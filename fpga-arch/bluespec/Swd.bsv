package Swd;

import Prescaler::*;

import StmtFSM::*;
import GetPut::*;
import Vector::*;
import ClientServer::*;

/// An AP or DP register.
typedef struct {
    Bit#(1) apndp;
    Bit#(2) addr;
} Register deriving (Eq, Bits);

/// A full 8-bits request packet.
typedef struct {
    Bit#(1) start;
    Bit#(1) apndp;
    Bit#(1) rnw;
    Bit#(2) addr;
    Bit#(1) parity;
    Bit#(1) stop;
    Bit#(1) park;
} RequestPacket deriving (Eq, Bits);

/// A transaction status.
typedef enum {
    OK,
    WAIT,
    FAULT,
    ERROR
} Status deriving (Eq, Bits, FShow);

/// The internal state of the SWD controller.
typedef enum {
    IDLE,
    PACKET,
    P_TRN,
    ACK,
    A_TRN,
    RDATA,
    WDATA,
    DONE,
    RESET
} State deriving (Eq, Bits, FShow);

/// A request, for either a Read or a Write
/// transaction.
typedef union tagged {
    struct {
        Register register;
        Bit#(32) wdata;
    } Write;

    struct {
        Register register;
    } Read;
} Request deriving (Eq, Bits);

/// A response, to either a Read or a Write
/// transaction.
typedef union tagged {
    struct {
        Status status;
    } Write;

    struct {
        Status status;
        Bit#(33) rdata;
    } Read;
} Response deriving (Eq, Bits);

/// The peripheral-facing pins of the SWD controller,
/// with swdio split into swd_in and swd_out.
(* always_ready, always_enabled *)
interface SWDControllerPins;
    (* prefix="" *) method Bit#(1) swclk;
    (* prefix="" *) method Action swd_in((* port="swd_in" *) Bit#(1) b);
    (* prefix="" *) method Bit#(1) swd_out;
    (* prefix="" *) method Bool out_en;
endinterface

/// The full SWD controller interface, with endpoints for
/// issuing Read and Write requests, and peripheral-facing
/// pins.
interface SWDController#(numeric type clk_divider);
    method Action reset;
    (* always_ready, always_enabled *) method Bool ready;
    interface Server#(Request, Response) rw;
    (* always_ready, always_enabled *) interface SWDControllerPins pins;
endinterface

module mkSWDController (SWDController#(clk_divider))
    provisos (
        Mul#(__a, 2, clk_divider),
        Add#(__b, 1, clk_divider)
    );

    // When a request comes in, the packet (and data, in case of a write request)
    // are registered, and swclk is kicked-off.
    // We then move sequencially through the steps of the transaction, shifting out
    // or in bits at a time, synchronously with the generated swclk rising/falling edges.
    // When the transaction is done, the transaction status is updated and marked
    // as Valid, triggering the release of the Get interface of the R/W server.
    //
    // The tricky thing, however, is to coordinate the state changes with the rising
    // and falling edges of the SWD clock.
    // Indeed we want to say that on the rising edge of swclk, meaning when it is zero
    // but will be one in the next cycle, we want to do a certain operation, that depends
    // on which step of the transaction we are in, i.e. which state.
    // Thus the state must have been updated *before*, on the cycle immediately preceding
    // the cycle itself preceding swclk == 1. 
    // This is what [prescaler.pre_rising] is for.

    Prescaler#(clk_divider) prescaler <- mkPrescaler();

    // Status and ACK of the current transaction.
    Reg#(Maybe#(Status)) status <- mkReg(tagged Invalid);
    Reg#(Vector#(3, Bit#(1))) ack <- mkReg(unpack(0));

    // Controller pins.
    Reg#(Bit#(1)) swd_out <- mkReg(0);
    Wire#(Bit#(1)) swd_in <- mkDWire(0);
    Reg#(Bool) out_en <- mkReg(True);
    Reg#(Bit#(1)) swclk <- mkReg(0);
    
    // Inner state.
    Reg#(State) state <- mkReg(IDLE);
    Reg#(Bool) rnw <- mkRegU;
    Reg#(Vector#(8, Bit#(1))) packet <- mkRegU;
    Reg#(Vector#(33, Bit#(1))) data <- mkRegU;

    // Counter for tracking bits in the transfered packet/data.
    Reg#(Bit#(7)) cnt <- mkRegU;

    // Same-cycle signals
    PulseWire request_in <- mkPulseWire();
    PulseWire reset_in <- mkPulseWire();

    // Generate the SWD clock, whenever there is an 
    // ongoing transaction.
    rule do_swclk (state != IDLE);
        if (prescaler.rising) begin
            swclk <= 1;
        end
        else if (prescaler.falling) begin
            swclk <= 0;
        end
    endrule

    // SWDIO is treated as an input only when in
    // the ACK or RDATA phase.
    rule do_out_en;
        if ((state == ACK) || (state == RDATA)) begin
            out_en <= False;
        end
        else begin
            out_en <= True;
        end
    endrule

    // Stop idling when a request has been received.
    rule do_idle (state == IDLE);
        if (request_in) begin
            state <= PACKET;
            cnt <= 8;
        end
        else if (reset_in) begin
            state <= RESET;
            cnt <= 118;
        end
        else begin
            swclk <= 0;
            swd_out <= 0;
        end
    endrule

    // Shift out the reset and switch sequence
    rule do_reset (state == RESET);
        if (prescaler.rising) begin
            // 51 cycles with swdio high (the specification says
            // "more than 50", we err on the side on caution and
            // take it to mean strictly more)
            if (cnt > 67) begin
                swd_out <= 1;
                cnt <= cnt - 1;
            end
            // followed by the 16 bits of the JTAG-to-SWD switching
            // sequence (bits 67 to 52 included)
            else if (cnt > 51) begin
                let switch_sequence = 16'hE79E;
                swd_out <= switch_sequence[67 - cnt];
                cnt <= cnt - 1;
            end
            // and finally 51 more cycles high
            // (bits 51 to 1, because the case cnt == 0 is preempted
            // by the pre_rising condition below)
            else begin
                swd_out <= 1;
                cnt <= cnt - 1;
            end
        end

        else if (prescaler.pre_rising && (cnt == 0)) begin
            state <= IDLE;
        end
    endrule

    // Shift out the command packet.
    rule do_packet (state == PACKET);
        if (prescaler.rising) begin
            // On every rising edge of the generated swclk, we need to shift out a
            // new bit of the packet
            swd_out <= packet[0];
            packet <= shiftInAtN(packet, 0);
            cnt <= cnt - 1;
        end
        
        // If we have shifted out the last bit of the packet,
        // and the next swclk rising edge is upcoming shortly,
        // we need to pre-emptively transition to the next state (the TRN period)
        // so that the corresponding rule is enabled when prescaler.rising becomes true,
        // so that it can actually do something useful on the very same cycle
        // where swclk is going to be high.
        else if (prescaler.pre_rising && (cnt == 0)) begin 
            state <= P_TRN; 
        end

    endrule

    // Shift out a TRN bit immediately following the packet.
    rule do_p_trn (state == P_TRN);
        if (prescaler.rising) begin
            swd_out <= 0;
        end

        else if (prescaler.pre_rising) begin 
            cnt <= 3;
            state <= ACK; 
        end
    endrule

    // Shift in the received ACK, by sampling the swd_in line in the
    // middle of the swclk cycles.
    rule do_ack (state == ACK);
        if (prescaler.rising) begin
            cnt <= cnt - 1;
        end

        else begin
            if (prescaler.falling) begin
                ack <= shiftInAt0(ack, swd_in);
            end

            if (prescaler.pre_rising && (cnt == 0)) begin
                // If we're shifting in the last ACK bit, next up will either
                // be a TRN period or the RDATA, depending on wether the current
                // request is a Read or a Write.
                if (rnw) begin
                    cnt <= 33;
                    state <= RDATA;
                end
                else begin
                    state <= A_TRN;
                end
            end
        end
    endrule

    // Shift out a TRN bit immediately following the ACK.
    // If the ACK is OK, go through with the DATA phase,
    // otherwise abort.
    rule do_a_trn (state == A_TRN);
        if (prescaler.rising) begin
            swd_out <= 0;
        end

        else if (prescaler.pre_rising) begin
            case (pack(ack)) matches
                3'b100:  
                    begin
                        cnt <= 33;
                        state <= WDATA;
                    end
                default: 
                    begin
                        cnt <= 1;
                        state <= DONE;
                    end
            endcase
        end
    endrule

    // Shift in the 32-bits read data, plus parity bit.
    rule do_rdata (state == RDATA);
        if (prescaler.rising) begin
            cnt <= cnt - 1;
        end

        else begin
            if (prescaler.falling) begin
                data <= shiftInAt0(data, swd_in);
            end

            if (prescaler.pre_rising && (cnt == 0)) begin
                cnt <= 1;
                state <= DONE;
            end
        end
    endrule

    // Shift out the 32-bits write data, and parity bit.
    rule do_wdata (state == WDATA);
        if (prescaler.rising) begin
            swd_out <= data[0];
            data <= shiftInAtN(data, 0);
            cnt <= cnt - 1;
        end

        else if (prescaler.pre_rising && (cnt == 0)) begin 
            cnt <= 1;
            state <= DONE; 
        end
    endrule

    // We're done. Update the status but keep swclk going for 
    // a full period, and then go back to IDLE.
    rule do_done (state == DONE);
        if (prescaler.rising) begin
            cnt <= cnt - 1;

            case (pack(ack)) matches
                3'b100: status <= Valid(OK);
                3'b010: status <= Valid(WAIT);
                3'b001: status <= Valid(FAULT);
                default: status <= Valid(ERROR);
            endcase
        end

        else if (prescaler.pre_rising && (cnt == 0)) begin
            state <= IDLE;
        end
    endrule

    // For debug purposes.
    rule log;
        $display($format("state: ") + fshow(state), ", swclk: %b, swd_out: %b, swd_in: %b, out_en: %b", 
                swclk, swd_out, swd_in, out_en);
    endrule

    // Interface methods and subinterfaces
    //
    method Bool ready = (state == IDLE);
    method Action reset if (state == IDLE);
        reset_in.send();
    endmethod

    interface Server rw;
        interface Put request;
            method Action put(req) if ((state == IDLE) && !isValid(status));
                case (req) matches
                    tagged Write .w_in : begin
                        let apndp = w_in.register.apndp;
                        let addr = w_in.register.addr;
                        let p = apndp ^ 0 ^ addr[0] ^ addr[1];
                        packet <= unpack(pack(RequestPacket { 
                                    start: 1, 
                                    apndp: apndp, 
                                    rnw: 0, 
                                    addr: addr, 
                                    parity: p, 
                                    stop: 0, 
                                    park: 1 }));
                        data <= append(unpack(w_in.wdata), replicate(parity(w_in.wdata)));
                        rnw <= False;
                        request_in.send();
                    end
                    tagged Read .r_in : begin
                        let apndp = r_in.register.apndp;
                        let addr = r_in.register.addr;
                        let p = apndp ^ 0 ^ addr[0] ^ addr[1];
                        packet <= unpack(pack(RequestPacket { 
                                    start: 1, 
                                    apndp: apndp, 
                                    rnw: 1, 
                                    addr: addr, 
                                    parity: p, 
                                    stop: 0, 
                                    park: 1 }));
                        rnw <= True;
                        request_in.send();
                    end
                endcase
            endmethod
        endinterface

        interface Get response;
            method ActionValue#(Response) get() if ((state == IDLE) && isValid(status));
                let transaction_status = fromMaybe(?, status);
                Response ret;
                ret = rnw ? tagged Read { status: transaction_status, rdata: pack(data) } : 
                            tagged Write { status: transaction_status };

                // reset state
                status <= tagged Invalid;
                data <= unpack(0);
                packet <= unpack(0);

                return ret;
            endmethod
        endinterface
    endinterface

    interface SWDControllerPins pins;
        method swclk = swclk;
        method swd_out = swd_out;
        method Action swd_in(b);
            swd_in <= b;
        endmethod
        method out_en = out_en;
    endinterface
endmodule

module mkSWDTest (Empty);
    SWDController#(2) swd_controller <- mkSWDController();
    let pins = swd_controller.pins;

    Reg#(Vector#(2, Bit#(1))) swclk <- mkReg(unpack(0));
    Reg#(Vector#(42, Bit#(1))) sampled <- mkReg(unpack(0));
    Reg#(Vector#(36, Bit#(1))) ack_rdata <- mkReg(unpack({unpack(0), 3'b001}));
    Reg#(Bool) en <- mkReg(False);

    rule do_shift;
        swclk <= shiftInAtN(swclk, pins.swclk);

        // Sample swd_out on falling edges, when enabled
        if ((swclk[0] == 1) && (swclk[1] == 0) && pins.out_en()) begin
            sampled <= shiftInAtN(sampled, pins.swd_out);
        end

        // Output ACK [+ RDATA] when asked for it
        if ((swclk[0] == 0) && (swclk[1] == 1) && !pins.out_en()) begin
            ack_rdata <= shiftInAtN(ack_rdata, 0);
        end
    endrule

    rule do_swd_in (!pins.out_en());
        pins.swd_in(ack_rdata[0]);
    endrule

    mkAutoFSM(seq
        swd_controller.reset();

        swd_controller.rw.request.put(
            tagged Write { register: Register { apndp: 1, addr: 2'b10 }, wdata: 0 });
        action
            let resp <- swd_controller.rw.response.get();
            case (resp) matches
                tagged Write .w_out:
                    $display("Status is: ", fshow(w_out.status));
                default:
                    $display("ERROR");
            endcase
        endaction

        action
            swclk <= unpack(0);
            sampled <= (unpack(0));
            // 0xf00dbabe, with parity (0)
            ack_rdata <= (unpack({unpack(33'b011111010101110110110000000011110), 3'b001}));
        endaction

        swd_controller.rw.request.put(tagged Read { register: Register { apndp: 1, addr: 2'b10 } });
        action
            let resp <- swd_controller.rw.response.get();
            case (resp) matches
                tagged Read .r_out: begin
                    $display("Status is: ", fshow(r_out.status));
                    Vector#(32, Bit#(1)) rdata = take(unpack(r_out.rdata));
                    $display("Rdata is: 0x%h", pack(rdata));
                end
                default:
                    $display("ERROR");
            endcase
        endaction
    endseq);
endmodule

endpackage
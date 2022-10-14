#!/usr/bin/python3
#
# This file is part of Scaffold
#
# Scaffold is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# Copyright 2019 Ledger SAS, written by Olivier Hériveaux


"""
This is a custom extension for sphinx to generate modules figures.
"""


import os.path
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from hashlib import sha1
import matplotlib
# Change backend to agg as workaround for import troubles with tkinter when
# building with readthedocs.io docker image.
matplotlib.use('agg')
import matplotlib.pyplot as plt  # noqa
import matplotlib.lines as lines  # noqa
import matplotlib.patches as patches  # noqa


def make_fig(path, inputs, outputs):
    # Outputs with '*' goes back to the left matrix.
    # Count how many of them we have.
    feedback_signals = []
    for i in range(len(outputs)):
        if outputs[i][-1] == '*':
            outputs[i] = outputs[i][:-1]  # Remove the '*' marker
            feedback_signals.append(outputs[i])

    line_width = 1
    # Head length and head width for arrows
    hl = 0.25
    hw = hl * 0.75
    box_w = 6
    box_left = -box_w//2
    box_right = -box_left
    top = 1
    text_margin = 0.2
    box_h = max(len(inputs), len(outputs)) + 1
    box_bottom = -box_h+1
    arrow_length_left = 1
    arrow_length_right = 1 + len(feedback_signals)
    area_w = box_w + arrow_length_left + arrow_length_right + 2
    area_h = box_h + 2 + len(feedback_signals)

    # Setup plot size and bounds
    plt.figure(figsize=(area_w * 0.3, area_h * 0.3), dpi=75)
    ax = plt.axes()

    r = patches.Rectangle(
        (box_left, box_bottom), box_w, box_h, fill=False, lw=line_width)
    ax.add_patch(r)

    for i, name in enumerate(inputs):
        ax.arrow(
            box_left - arrow_length_left, -i, arrow_length_left - hl, 0,
            fc='k', ec='k', head_length=hl, head_width=hw, lw=line_width)
        ax.annotate(
            text=name, xy=(box_left + text_margin, -i),
            horizontalalignment='left', verticalalignment='center')

    num_feedback = 0

    for i, name in enumerate(outputs):
        ax.arrow(
            box_right, -i, arrow_length_right - hl, 0, fc='k', ec='k',
            head_length=hl, head_width=hw, lw=line_width)
        ax.annotate(
            text=name, xy=(box_right - text_margin, -i),
            horizontalalignment='right', verticalalignment='center')
        if name in feedback_signals:
            x0 = box_right + num_feedback + 1
            x1 = box_left - 1
            y0 = -i
            y1 = box_bottom - 1 - num_feedback
            line = lines.Line2D(
                [x0, x0], [y0, y1], color='black', linewidth=line_width)
            ax.add_line(line)
            ax.arrow(
                x0, y1, x1 - x0, 0, fc='k', ec='k', head_length=hl,
                head_width=hw, lw=line_width)
            plt.scatter(x0, y0, s=6, color='black')
            num_feedback += 1

    # Configure axis after everything has been drawn, otherwise plotting
    # anything for instance with plt.scatter(...) will change de view.
    ax.axis('equal')
    ax.set_xbound(
        box_left - arrow_length_left - 1, box_right + arrow_length_right + 1)
    ax.set_ybound(box_bottom - 1 - len(feedback_signals), top+1)
    ax.axis('off')

    # Create the directories before trying to save.
    # It seems sphinx may forget to create them.
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    plt.savefig(path, transparent=True)


class ModBoxNode(nodes.Element):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.outputs = []


def io_list(s):
    return list(
        filter(
            lambda x: len(x) > 0, (x.strip() for x in s.split(','))))


class ModBoxDirective(Directive):
    has_content = True
    option_spec = {
        'inputs': directives.unchanged,
        'outputs': directives.unchanged}

    def run(self):
        node = ModBoxNode()
        node.inputs = io_list(self.options['inputs'])
        node.outputs = io_list(self.options['outputs'])
        return [node]


def visit_modbox_node(self, node):
    hashkey = '-'.join(node.inputs + node.outputs)
    fname = 'modbox-{0}.svg'.format(sha1(hashkey.encode()).hexdigest())
    outfn = os.path.join(self.builder.outdir, self.builder.imagedir, fname)
    make_fig(outfn, node.inputs, node.outputs)
    # Generate HTML tag
    self.body.append('<center><img src="_images/{0}"/></center>'.format(fname))


def depart_modbox_node(self, node):
    pass


def setup(app):
    app.add_node(ModBoxNode, html=(visit_modbox_node, depart_modbox_node))
    app.add_directive('modbox', ModBoxDirective)

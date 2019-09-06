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


import matplotlib
# Change backend to agg as workaround for import troubles with tkinter when
# building with readthedocs.io docker image.
matplotlib.use('agg')
import matplotlib.pyplot as plt
import matplotlib.lines as lines
import matplotlib.patches as patches
import os.path
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from hashlib import sha1


def make_fig(path, inputs, outputs):
    line_width = 1
    # Head length and head width for arrows
    hl = 0.25
    hw = hl * 0.75
    box_w = 6
    left = -box_w//2
    right = -left
    top = 1
    text_margin = 0.2
    box_h = max(len(inputs), len(outputs)) + 1
    bottom = -box_h+1
    arrow_length = 1
    area_w = box_w + arrow_length * 2 + 2
    area_h = box_h + 2

    # Setup plot size and bounds
    plt.figure(figsize=(area_w * 0.3, area_h * 0.3), dpi=75)
    ax = plt.axes()
    ax.axis('equal')
    ax.set_xbound(-area_w/2, area_w/2)
    ax.set_ybound(bottom-1, top+1)
    ax.axis('off')

    r = patches.Rectangle((left, bottom), box_w, box_h, fill=False,
        lw=line_width)
    ax.add_patch(r)

    for i, name in enumerate(inputs):
        ax.arrow(left - arrow_length, -i, arrow_length - hl, 0, fc='k', ec='k',
            head_length=hl, head_width=hw, lw=line_width)
        ax.annotate(s=name, xy=(left + text_margin, -i),
            horizontalalignment='left', verticalalignment='center')

    for i, name in enumerate(outputs):
        ax.arrow(right, -i, arrow_length - hl, 0, fc='k', ec='k',
            head_length=hl, head_width=hw, lw=line_width)
        ax.annotate(s=name, xy=(right - text_margin, -i),
            horizontalalignment='right', verticalalignment='center')

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
            lambda x: len(x) > 0,
            (x.strip() for x in s.split(',')) ) )


class ModBoxDirective(Directive):
    has_content = True
    option_spec = {
        'inputs': directives.unchanged,
        'outputs': directives.unchanged }

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


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


from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="donjon-scaffold",
    version="0.7.9",
    author="Olivier Heriveaux",
    description="Python3 API for the Scaffold board",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Ledger-Donjon/scaffold",
    install_requires=["pyserial", "crcmod"],
    packages=find_packages(),
    python_requires=">=3.6")

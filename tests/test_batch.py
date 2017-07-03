#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test batch control
"""
from __future__ import print_function

from os.path import abspath, dirname
import sys

import io
import tempfile
import wx

import numpy as np
import unittest

import dclab


# Add parent directory to beginning of path variable
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from shapeout.__main__ import setup_lang
from shapeout.gui import frontend


from helper_methods import retreive_tdms, example_data_sets, cleanup


class TestSimple(unittest.TestCase):
    '''Test ShapeOut batch'''
    def setUp(self):
        '''Create the GUI'''
        setup_lang()
        self.frame = frontend.Frame("test")

    def tearDown(self):
        cleanup()
        self.frame.Destroy()


    def test_batch(self):
        # load data
        tdms_path = retreive_tdms(example_data_sets[0])
        ds = dclab.new_dataset(tdms_path)
        # start session
        self.frame.NewAnalysis([ds])
        
        # Disable new option "remove invalid events" which removes the last
        # event and invalidates this test case:
        # new analysis overrides filtering. -> Change filtering afterwards.
        ds.config["filtering"]["remove invalid events"] = False
        ds.apply_filter()

        batch = self.frame.OnMenuBatchFolder()
        batch.out_tsv_file=tempfile.mkstemp(".tsv", "shapeout_batch")[1]
        batch.tdms_files=[tdms_path]
        batch.OnBatch()
        
        with io.open(batch.out_tsv_file) as fd:
            data = fd.readlines()
        
        header = [d.strip().lower() for d in data[0].strip("# ").split("\t")]
        values = [d.strip() for d in data[1].strip("# ").split("\t")]
        soll={"%-gated": 100,
              "events": 156,
              "flow rate": 0.12,
              "mean deformation": 1.3096144795e-01}

        for key in soll:
            idx = header.index(key)
            assert np.allclose(float(values[idx]), soll[key])

        batch.Destroy()


if __name__ == "__main__":
    unittest.main()

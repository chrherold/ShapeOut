#!/usr/bin/python
# -*- coding: utf-8 -*-
""" ShapeOut - wx frontend components

"""
from __future__ import division, print_function, unicode_literals

import os
import platform
import sys
import traceback
import warnings

import imageio.plugins.ffmpeg as imioff
import numpy as np
import wx

import dclab


from .. import analysis
from ..configuration import ConfigurationFile
from .. import tlabwrap
from ..util import findfile

from . import autosave
from . import batch
from .controls import ControlPanel
from .explorer import ExplorerPanel
from . import export
from . import gaugeframe
from . import help
from . import misc
from . import plot_export
from . import plot_main
from . import session
from . import update
from . import video



class ExceptionDialog(wx.MessageDialog):
    """"""
    def __init__(self, msg):
        """Constructor"""
        wx.MessageDialog.__init__(self, None, msg, _("Error"),
                                          wx.OK|wx.ICON_ERROR)   



class Frame(gaugeframe.GaugeFrame):
    """"""
    def __init__(self, version):
        """Constructor"""
        self.config = ConfigurationFile(findfile("shapeout.cfg"))
        self.version = version
        #size = (1300,900)
        size = (1200,700)
        minsize = (900, 700)
        gaugeframe.GaugeFrame.__init__(self, None, -1,
                title = _("%(progname)s - version %(version)s") % {
                        "progname": "ShapeOut", "version": version},
                size = size)
        self.SetMinSize(minsize)
        
        sys.excepthook = MyExceptionHook

        ## Menus, Toolbar
        self.InitUI()

        self.sp = wx.SplitterWindow(self, style=wx.SP_THIN_SASH)
        # This is necessary to prevent "Unsplit" of the SplitterWindow:
        self.sp.SetMinimumPaneSize(100)
        
        self.spright = wx.SplitterWindow(self.sp, style=wx.SP_THIN_SASH)
        if platform.system() == "Linux":
            sy = 270
        else:
            sy = 230
            
        self.spright.SetMinimumPaneSize(sy)
        
        # Splitter Window for control panel and cell view
        self.sptop = wx.SplitterWindow(self.spright, style=wx.SP_THIN_SASH)
        self.sptop.SetMinimumPaneSize(sy)

        # Controls
        self.PanelTop = ControlPanel(self.sptop, frame=self)
        
        # Cell Images
        self.ImageArea = video.ImagePanel(self.sptop, frame=self)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.PanelTop, 2, wx.ALL|wx.EXPAND, 5)
        sizer.Add(self.ImageArea, 1, wx.ALL|wx.EXPAND, 5)
        
        self.sptop.SplitVertically(self.PanelTop, self.ImageArea, sy)
        self.sptop.SetSashGravity(.46)
        
        # Main Plots
        self.PlotArea = plot_main.PlotPanel(self.spright, self)

        self.spright.SplitHorizontally(self.sptop, self.PlotArea, sy)
        
        ## left panel (file selection)
        ## We need a splitter window here
        self.PanelLeft = ExplorerPanel(self.sp, self)
        self.PanelLeft.BindAnalyze(self.NewAnalysis)

        self.sp.SplitVertically(self.PanelLeft, self.spright,
                                self.PanelLeft.normal_width)

        # We set this to 100 again after show is complete.
        self.spright.SetMinimumPaneSize(sy)
       
        # Fake analysis
        ddict = {"area" : np.arange(10)*30,
                 "defo" : np.arange(10)*.02}
        rtdc_ds = dclab.RTDC_DataSet(ddict=ddict)
        self.NewAnalysis([rtdc_ds])

        ## Go
        self.Centre()
        self.Show()
        self.Maximize()
        
        self.spright.SetMinimumPaneSize(100)
        self.sptop.SetMinimumPaneSize(100)
        
        # Set window icon
        try:
            self.MainIcon = misc.getMainIcon()
            wx.Frame.SetIcon(self, self.MainIcon)
        except:
            self.MainIcon = None


    def InitRun(self, session_file=None):
        """Performs the first tasks after the publication starts
        
        - start autosaving
        - check for updates
        - download ffmpeg
        """
        # Check if we have an autosaved session that we did not delete
        recover = autosave.check_recover(self)
        
        # Load session file if provided
        if session_file is not None and not recover:
            self.OnMenuLoad(session_file=session_file)
            
        # Search for updates
        update.Update(self)

        # Start autosaving
        autosave.autosave_run(self)

        # download ffmpeg for imageio
        try:
            imioff.get_exe()
        except imioff.NeedDownloadError:
            # Tell the user that we will download ffmpeg now!
            msg = "ShapeOut needs to download `FFMPEG` in order " \
                 +"to display and export video data. Please make " \
                 +"sure you are connected to the internet and " \
                 +"click OK. Depending on your connection, this" \
                 +"may take a while. Please be patient. There" \
                 +"is no progress dialog."
            dlg = wx.MessageDialog(parent=None,
                                   message=msg, 
                                   caption="FFMPEG download",
                                   style=wx.OK|wx.CANCEL|wx.ICON_QUESTION)

            if dlg.ShowModal() == wx.ID_OK:
                imioff.download()



    def InitUI(self):
        """Menus, Toolbar, Statusbar"""
        
        ## Menubar
        self.menubar = wx.MenuBar()
        self.SetMenuBar(self.menubar)
        
        ## File menu
        fileMenu = wx.Menu()
        self.menubar.Append(fileMenu, _('&File'))
        # data
        fpath = fileMenu.Append(wx.ID_REPLACE, _('Find Measurements'), 
                                _('Select .tdms file location'))
        self.Bind(wx.EVT_MENU, self.OnMenuSearchPath, fpath)
        fpathadd = fileMenu.Append(wx.ID_FIND, _('Add Measurements'), 
                                _('Select .tdms file location'))
        self.Bind(wx.EVT_MENU, self.OnMenuSearchPathAdd, fpathadd)
        # clear measurements
        fpathclear = fileMenu.Append(wx.ID_CLEAR, _('Clear Measurements'), 
                             _('Clear unchecked items in project list'))
        self.Bind(wx.EVT_MENU, self.OnMenuClearMeasurements, fpathclear)
        fileMenu.AppendSeparator()
        # save
        fsave = fileMenu.Append(wx.ID_SAVE, _('Save Session'), 
                                _('Select .zmso file'))
        self.Bind(wx.EVT_MENU, self.OnMenuSave, fsave)
        # load
        fload = fileMenu.Append(wx.ID_OPEN, _('Open Session'), 
                                _('Select .zmso file'))
        self.Bind(wx.EVT_MENU, self.OnMenuLoad, fload)
        fileMenu.AppendSeparator()
        # quit
        fquit = fileMenu.Append(wx.ID_EXIT, _('Quit'), 
                                _('Quit ShapeOut'))
        self.Bind(wx.EVT_MENU, self.OnMenuQuit, fquit)
        
        ## Export Data menu
        exportDataMenu = wx.Menu()
        self.menubar.Append(exportDataMenu, _('Export &Data'))
        e2tsv = exportDataMenu.Append(wx.ID_ANY, _('All &event data (*.tsv)'), 
                _('Export the plotted event data as tab-separated values'))
        self.Bind(wx.EVT_MENU, self.OnMenuExportEventsTSV, e2tsv)
        e2fcs = exportDataMenu.Append(wx.ID_ANY, _('All &event data (*.fcs)'), 
                _('Export the plotted event data as flow cytometry standard files'))
        self.Bind(wx.EVT_MENU, self.OnMenuExportEventsFCS, e2fcs)
        e2stat = exportDataMenu.Append(wx.ID_ANY, _('Computed &statistics (*.tsv)'), 
                       _('Export the statistics data as tab-separated values'))
        self.Bind(wx.EVT_MENU, self.OnMenuExportStatistics, e2stat)
        e2avi = exportDataMenu.Append(wx.ID_ANY, _('All &event images (*.avi)'), 
                _('Export the event images as video files'))
        self.Bind(wx.EVT_MENU, self.OnMenuExportEventsAVI, e2avi)
        
        ## Export Plot menu
        exportPlotMenu = wx.Menu()
        self.menubar.Append(exportPlotMenu, _('Export &Plot'))

        e2pdf = exportPlotMenu.Append(wx.ID_ANY, _('Graphical &plot (*.pdf)'), 
                       _('Export the plot as a portable document file'))
        self.Bind(wx.EVT_MENU, self.OnMenuExportPDF, e2pdf)
        # export SVG disabled:
        # The resulting graphic is not better than the PDF and axes are missing
        #e2svg = exportPlotMenu.Append(wx.ID_ANY, _('Graphical &plot (*.svg)'), 
        #               _('Export the plot as a scalable vector graphics file'))
        #self.Bind(wx.EVT_MENU, self.OnMenuExportSVG, e2svg)
        # export PNG disabled:
        # https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut/issues/62
        #e2png = exportMenu.Append(wx.ID_ANY, _('Graphical &plot (*.png)'), 
        #               _('Export the plot as a portable network graphic'))
        #self.Bind(wx.EVT_MENU, self.OnMenuExportPNG, e2png)


        ## Batch menu
        batchMenu = wx.Menu()
        self.menubar.Append(batchMenu, _('&Batch'))
        b_filter = batchMenu.Append(wx.ID_ANY, _('&Statistical analysis'), 
                    _('Apply one filter setting to multiple measurements.'))
        self.Bind(wx.EVT_MENU, self.OnMenuBatchFolder, b_filter)
        
        ## Help menu
        helpmenu = wx.Menu()
        self.menubar.Append(helpmenu, _('&Help'))
        menuSoftw = helpmenu.Append(wx.ID_ANY, _("&Software"),
                                    _("Information about the software used"))
        self.Bind(wx.EVT_MENU, self.OnMenuHelpSoftware, menuSoftw)
        menuAbout = helpmenu.Append(wx.ID_ABOUT, _("&About"),
                                    _("Information about this program"))
        self.Bind(wx.EVT_MENU, self.OnMenuHelpAbout, menuAbout)
        
        ## Toolbar
        self.toolbar = wx.ToolBar(self, style=wx.TB_FLAT|wx.TB_HORIZONTAL|wx.TB_NODIVIDER)
        iconsize = (36,36)
        self.toolbar.SetToolBitmapSize(iconsize)
        
        names = [['Load Measurements', wx.ID_REPLACE, wx.ART_FIND_AND_REPLACE],
                 ['Add Measurements', wx.ID_FIND, wx.ART_FIND],
                 ['Save Session', wx.ID_SAVE, wx.ART_FILE_SAVE_AS],
                 ['Open Session', wx.ID_OPEN, wx.ART_FILE_OPEN],
                ]
        
        def add_icon(name):
            self.toolbar.AddLabelTool(name[1],
                                      _(name[0]),
                                      bitmap=wx.ArtProvider.GetBitmap(
                                                                  name[2],
                                                                  wx.ART_TOOLBAR,
                                                                  iconsize))
        
        def add_image(name, height=-1, width=-1):
            png = wx.Image(findfile(name), wx.BITMAP_TYPE_ANY)
            image = wx.StaticBitmap(self.toolbar, -1, png.ConvertToBitmap(), size=(width,height))
            self.toolbar.AddControl(image)
        
        for name in names:
            add_icon(name)
        
        add_image("transparent_h50.png", width=75, height=iconsize[0])
        add_image("zm_logo_h36.png")        

        try:
            # This only works with wxPython3
            self.toolbar.AddStretchableSpace()
        except:
            pass

        add_image("shapeout_logotype_h36.png")

        try:
            # This only works with wxPython3
            self.toolbar.AddStretchableSpace()
        except:
            pass
        
        add_image("transparent_h50.png", height=iconsize[0])
        add_icon(['Quit', wx.ID_EXIT, wx.ART_QUIT])
        self.toolbar.Realize()
        self.SetToolBar(self.toolbar)
        #self.background_color = self.statusbar.GetBackgroundColour()
        #self.statusbar.SetBackgroundColour(self.background_color)
        #self.statusbar.SetBackgroundColour('RED')
        #self.statusbar.SetBackgroundColour('#E0E2EB')
        #self.statusbar.Refresh()
        
        self.Bind(wx.EVT_CLOSE, self.OnMenuQuit)


    def NewAnalysis(self, data, search_path="./"):
        """ Create new analysis object and show data """
        wx.BeginBusyCursor()
        # Get Plotting and Filtering parameters from previous analysis
        if hasattr(self, "analysis"):
            # Get Plotting and Filtering parameters from previous analysis
            newcfg = {}
            for key in ["analysis", "calculation", "filtering", "plotting"]:
                newcfg[key] = self.analysis.GetParameters(key)
            contour_colors = self.analysis.GetContourColors()
            self.analysis._clear()
        else:
            newcfg = {}
            contour_colors = None
        
        # Catch hash comparison warnings and display warning to the user
        with warnings.catch_warnings(record=True) as ww:
            warnings.simplefilter("always",
                                  category=analysis.HashComparisonWarning)
            anal = analysis.Analysis(data, search_path=search_path, config=newcfg)
            if len(ww):
                msg = "One or more files referred to in the chosen session "+\
                      "did not pass the hash check. Nevertheless, ShapeOut "+\
                      "loaded the data. The following warnings were issued:\n"
                msg += "".join([ "\n - "+w.message.message for w in ww ])
                dlg = wx.MessageDialog(None,
                                       _(msg),
                                       _('Hash mismatch warning'),
                                       wx.OK | wx.ICON_WARNING)
                dlg.ShowModal()

            # Set previous contour colors
            anal.SetContourColors(contour_colors)

        self.analysis = anal
        self.PanelTop.NewAnalysis(anal)
        self.PlotArea.Plot(anal)
        wx.EndBusyCursor()


    def OnMenuBatchFolder(self, e=None):
        return batch.BatchFilterFolder(self, self.analysis)


    def OnMenuClearMeasurements(self, e=None):
        tree = self.PanelLeft.htreectrl
        r = tree.GetRootItem()
        dellist = []
        # iterate through all measurements
        for c in r.GetChildren():
            for ch in c.GetChildren():
                # keep those:
                # - bold means it was analyzed
                # - checked means user wants to analyze next
                if not ch.IsChecked() and not ch.IsBold():
                    dellist.append(ch)
        for ch in dellist:
            tree.Delete(ch)
        dellist = []
        # find empty parents
        for c in r.GetChildren():
            if len(c.GetChildren()) == 0:
                dellist.append(c)
        for ch in dellist:
            tree.Delete(ch)


    def OnMenuExportEventsAVI(self, e=None):
        """Export the event image data to an avi file
        
        This will open a dialog for the user to select
        the target file name.
        """
        # Generate dialog
        export.export_event_images_avi(self, self.analysis)


    def OnMenuExportEventsFCS(self, e=None):
        """Export the event data of the entire analysis as fcs
        
        This will open a choice dialog for the user
        - which data (filtered/unfiltered)
        - which columns (Area, Deformation, etc)
        - to which folder should be exported 
        """
        # Generate dialog
        export.ExportAnalysisEventsFCS(self, self.analysis)


    def OnMenuExportEventsTSV(self, e=None):
        """Export the event data of the entire analysis as tsv
        
        This will open a choice dialog for the user
        - which data (filtered/unfiltered)
        - which columns (Area, Deformation, etc)
        - to which folder should be exported 
        """
        # Generate dialog
        export.ExportAnalysisEventsTSV(self, self.analysis)


    def OnMenuExportPDF(self, e=None):
        """ Saves plot container as PDF
        
        Uses heuristic methods to resize
        - the plot
        - the scatter plot markers
        and then changes everything back
        """
        plot_export.export_plot_pdf(self)


    def OnMenuExportSVG(self, e=None):
        """ Saves plot container as SVG
        
        Uses heuristic methods to resize
        - the plot
        - the scatter plot markers
        and then changes everything back
        """
        plot_export.export_plot_svg(self)


    def OnMenuExportPNG(self, e=None):
        """ Saves plot container as png
        
        """
        plot_export.export_plot_png(self)


    def OnMenuExportStatistics(self, e=None):
        """ Saves statistics results from tab to text file
        
        """
        export.export_statistics_tsv(self)


    def OnMenuHelpAbout(self, e=None):
        help.about()

    
    def OnMenuHelpSoftware(self, e=None):
        help.software()


    def OnMenuLoad(self, e=None, session_file=None):
        """ Load entire analysis """
        # Determine which session file to open
        if session_file is None:
            # User dialog
            dlg = wx.FileDialog(self, "Open session file",
                    self.config.get_dir(name="Session"), "",
                            "ShapeOut session (*.zmso)|*.zmso", wx.FD_OPEN)
            
            if dlg.ShowModal() == wx.ID_OK:
                self.config.set_dir(dlg.GetDirectory(), name="Session")
                fname = dlg.GetPath()
                dlg.Destroy()
            else:
                self.config.set_dir(dlg.GetDirectory(), name="Session")
                dlg.Destroy()
                return # nothing more to do here
        else:
            fname = session_file 

        session.open_session(fname, self)
        

    def OnMenuSearchPath(self, e=None):
        """ Set path of working directory
        
        Display Dialog to select folder and update Content of PanelLeft.
        This calls `PanelLeft.SetProjectTree`.
        """
        dlg = wx.DirDialog(self, _("Please select a directory"),
               defaultPath=self.config.get_dir(name="MeasurementList"))
        answer = dlg.ShowModal()
        if answer == wx.ID_OK:
            path = dlg.GetPath()
            self.config.set_dir(path, name="MeasurementList")
            dlg.Destroy()
            self.GaugeIndefiniteStart(
                                func=tlabwrap.GetTDMSTreeGUI,
                                func_args=(path,),
                                post_call=self.PanelLeft.SetProjectTree,
                                msg=_("Searching for .tdms files")
                                     )


    def OnMenuSearchPathAdd(self, e=None, add=True, path=None,
                            marked=[]):
        """ Convenience wrapper around OnMenuSearchPath"""
        if path is None:
            dlg = wx.DirDialog(self, _("Please select a directory"),
                   defaultPath=self.config.get_dir(name="MeasurementList"))
            answer = dlg.ShowModal()
            path = dlg.GetPath()
            self.config.set_dir(path, name="MeasurementList")
            dlg.Destroy()
            if answer != wx.ID_OK:
                return
            
        self.GaugeIndefiniteStart(
                        func=tlabwrap.GetTDMSTreeGUI,
                        func_args=(path,),
                        post_call=self.PanelLeft.SetProjectTree,
                        post_call_kwargs = {"add":add, "marked":marked},
                        msg=_("Searching for .tdms files")
                                 )

    def OnMenuQuit(self, e=None):
        if hasattr(self, "analysis") and self.analysis is not None:
            # Ask to save the session
            dial = wx.MessageDialog(self, 
                'Do you want to save the current Session?', 
                'Save Session?', 
                 wx.ICON_QUESTION | wx.CANCEL | wx.YES_NO | wx.NO_DEFAULT )
            result = dial.ShowModal()
            dial.Destroy()
            if result == wx.ID_CANCEL:
                return # abort
            elif result == wx.ID_YES:
                filename = self.OnMenuSaveSimple()
                if filename is None:
                    # User did not save session - abort
                    return
            
        # remove the autosaved file
        try:
            if os.path.exists(autosave.autosave_file):
                os.remove(autosave.autosave_file)
        except:
            pass
        os._exit(0)


    def OnMenuSave(self, e=None):
        """ Save configuration without measurement data """
        dlg = wx.FileDialog(self, "Save ShapeOut session", 
                    self.config.get_dir(name="Session"), "",
                    "ShapeOut session (*.zmso)|*.zmso",
                    wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            # Save everything
            path = dlg.GetPath()
            if not path.endswith(".zmso"):
                path += ".zmso"
            dirname = os.path.dirname(path)
            self.config.set_dir(dirname, name="Session")
            session.save_session(path, self.analysis)
            return path
        else:
            dirname = dlg.GetDirectory()
            self.config.set_dir(dirname, name="Session")
            dlg.Destroy()



def MyExceptionHook(etype, value, trace):
    """
    Handler for all unhandled exceptions.
 
    :param `etype`: the exception type (`SyntaxError`, `ZeroDivisionError`, etc...);
    :type `etype`: `Exception`
    :param string `value`: the exception error message;
    :param string `trace`: the traceback header, if any (otherwise, it prints the
     standard Python header: ``Traceback (most recent call last)``.
    """
    wx.GetApp().GetTopWindow()
    tmp = traceback.format_exception(etype, value, trace)
    exception = "".join(tmp)
 
    dlg = ExceptionDialog(exception)
    dlg.ShowModal()
    dlg.Destroy()     
    wx.EndBusyCursor()

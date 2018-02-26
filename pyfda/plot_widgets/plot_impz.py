# -*- coding: utf-8 -*-
#
# This file is part of the pyFDA project hosted at https://github.com/chipmuenk/pyfda
#
# Copyright © pyFDA Project Contributors
# Licensed under the terms of the MIT License
# (see file LICENSE in root directory for details)

"""
Widget for plotting impulse and general transient responses
"""
from __future__ import print_function, division, unicode_literals, absolute_import
import logging
logger = logging.getLogger(__name__)

from ..compat import QWidget, QEvent, Qt, pyqtSlot

import numpy as np
import scipy.signal as sig

import pyfda.filterbroker as fb
from pyfda.pyfda_lib import expand_lim, to_html, safe_eval
from pyfda.pyfda_rc import params # FMT string for QLineEdit fields, e.g. '{:.3g}'
from pyfda.plot_widgets.mpl_widget import MplWidget
#from mpl_toolkits.mplot3d.axes3d import Axes3D
from .plot_impz_ui import PlotImpz_UI


class PlotImpz(QWidget):
    """
    Construct a widget for plotting impulse and general transient responses
    """
    def __init__(self, parent):
        super(PlotImpz, self).__init__(parent)

        self.ACTIVE_3D = False
        self.ui = PlotImpz_UI(self) # create the UI part with buttons etc.

        # initial settings for line edit widgets
        self.f1 = self.ui.f1
        self.f2 = self.ui.f2

        self._construct_UI()

    def _construct_UI(self):
        """
        Create the top level UI of the widget, consisting of matplotlib widget
        and control frame.
        """
        
        #----------------------------------------------------------------------
        # mplwidget
        #----------------------------------------------------------------------
        self.mplwidget = MplWidget(self)
        self.mplwidget.layVMainMpl.addWidget(self.ui)
        self.mplwidget.layVMainMpl.setContentsMargins(*params['wdg_margins'])
        self.setLayout(self.mplwidget.layVMainMpl)

        #----------------------------------------------------------------------
        # SIGNALS & SLOTs
        #----------------------------------------------------------------------
        self.ui.ledN_points.editingFinished.connect(self.draw)
        # frequency widgets require special handling as they are scaled with f_s
        self.ui.ledFreq1.installEventFilter(self)
        self.ui.ledFreq2.installEventFilter(self)

        self.mplwidget.mplToolbar.sig_tx.connect(self.process_signals)
        self.ui.sig_tx.connect(self.process_signals)

        self.draw() # initial calculation and drawing

#------------------------------------------------------------------------------
    @pyqtSlot(object)
    def process_signals(self, sig_dict):
        """
        Process signals coming from the navigation toolbar
        """
        if 'update_view' in sig_dict or 'home' in sig_dict:
            self.update_view()
        elif 'enabled' in sig_dict:
            self.enable_ui(sig_dict['enabled'])
        elif 'draw' in sig_dict:
            self.draw()
        else:
            logger.error("Dict not understood: {0}".format(sig_dict))

#------------------------------------------------------------------------------
    def enable_ui(self, enabled):
        """
        Triggered when the toolbar is enabled or disabled
        """
        self.ui.frmControls.setEnabled(enabled)
        if enabled:
            # self.init_axes() # called by self.draw
            self.draw()

#------------------------------------------------------------------------------
    def eventFilter(self, source, event):
        """
        Filter all events generated by the monitored widgets. Source and type
        of all events generated by monitored objects are passed to this eventFilter,
        evaluated and passed on to the next hierarchy level.

        - When a QLineEdit widget gains input focus (`QEvent.FocusIn`), display
          the stored value from filter dict with full precision
        - When a key is pressed inside the text field, set the `spec_edited` flag
          to True.
        - When a QLineEdit widget loses input focus (`QEvent.FocusOut`), store
          current value normalized to f_S with full precision (only if
          `spec_edited`== True) and display the stored value in selected format
        """

        def _store_entry(source):
            if self.spec_edited:
                if source.objectName() == "stimFreq1":
                   self.f1 = safe_eval(source.text(), self.f1 * fb.fil[0]['f_S'],
                                            return_type='float') / fb.fil[0]['f_S']
                   source.setText(str(params['FMT'].format(self.f1 * fb.fil[0]['f_S'])))

                elif source.objectName() == "stimFreq2":
                   self.f2 = safe_eval(source.text(), self.f2 * fb.fil[0]['f_S'],
                                            return_type='float') / fb.fil[0]['f_S']
                   source.setText(str(params['FMT'].format(self.f2 * fb.fil[0]['f_S'])))

                self.spec_edited = False # reset flag
                self.draw()

#        if isinstance(source, QLineEdit): 
#        if source.objectName() in {"stimFreq1","stimFreq2"}:
        if event.type() in {QEvent.FocusIn,QEvent.KeyPress, QEvent.FocusOut}:
            if event.type() == QEvent.FocusIn:
                self.spec_edited = False
                self.load_fs()
            elif event.type() == QEvent.KeyPress:
                self.spec_edited = True # entry has been changed
                key = event.key()
                if key in {Qt.Key_Return, Qt.Key_Enter}:
                    _store_entry(source)
                elif key == Qt.Key_Escape: # revert changes
                    self.spec_edited = False
                    if source.objectName() == "stimFreq1":                    
                        source.setText(str(params['FMT'].format(self.f1 * fb.fil[0]['f_S'])))
                    elif source.objectName() == "stimFreq2":                    
                        source.setText(str(params['FMT'].format(self.f2 * fb.fil[0]['f_S'])))

            elif event.type() == QEvent.FocusOut:
                _store_entry(source)

        # Call base class method to continue normal event processing:
        return super(PlotImpz, self).eventFilter(source, event)

#-------------------------------------------------------------        
    def load_fs(self):
        """
        Reload sampling frequency from filter dictionary and transform
        the displayed frequency spec input fields according to the units
        setting (i.e. f_S). Spec entries are always stored normalized w.r.t. f_S 
        in the dictionary; when f_S or the unit are changed, only the displayed values
        of the frequency entries are updated, not the dictionary!

        load_fs() is called during init and when the frequency unit or the
        sampling frequency have been changed.

        It should be called when sigSpecsChanged or sigFilterDesigned is emitted
        at another place, indicating that a reload is required.
        """

        # recalculate displayed freq spec values for (maybe) changed f_S
        if self.ui.ledFreq1.hasFocus():
            # widget has focus, show full precision
            self.ui.ledFreq1.setText(str(self.f1 * fb.fil[0]['f_S']))
        elif self.ui.ledFreq2.hasFocus():
            # widget has focus, show full precision
            self.ui.ledFreq2.setText(str(self.f2 * fb.fil[0]['f_S']))
        else:
            # widgets have no focus, round the display
            self.ui.ledFreq1.setText(
                str(params['FMT'].format(self.f1 * fb.fil[0]['f_S'])))
            self.ui.ledFreq2.setText(
                str(params['FMT'].format(self.f2 * fb.fil[0]['f_S'])))

#------------------------------------------------------------------------------
    def init_axes(self):
        # clear the axes and (re)draw the plot
        #
        try:
            self.mplwidget.fig.delaxes(self.ax_r)
            self.mplwidget.fig.delaxes(self.ax_i)
        except (KeyError, AttributeError, UnboundLocalError):
            pass

        if self.cmplx and self.ui.chkPltResp.isChecked():
            self.ax_r = self.mplwidget.fig.add_subplot(211)
            self.ax_r.clear()
            self.ax_r.get_xaxis().tick_bottom() # remove axis ticks on top
            self.ax_r.get_yaxis().tick_left() # remove axis ticks right

            self.ax_i = self.mplwidget.fig.add_subplot(212, sharex = self.ax_r)
            self.ax_i.clear()
            self.ax_i.get_xaxis().tick_bottom() # remove axis ticks on top
            self.ax_i.get_yaxis().tick_left() # remove axis ticks right

        else:
            self.ax_r = self.mplwidget.fig.add_subplot(111)
            self.ax_r.clear()
            self.ax_r.get_xaxis().tick_bottom() # remove axis ticks on top
            self.ax_r.get_yaxis().tick_left() # remove axis ticks right

        self.mplwidget.fig.subplots_adjust(hspace = 0.5)  

        if self.ACTIVE_3D: # not implemented / tested yet
            self.ax3d = self.mplwidget.fig.add_subplot(111, projection='3d')

#------------------------------------------------------------------------------
    def calc(self):
        """
        (Re-)calculate stimulus x[n] and filter response y[n]
        """
        # calculate time vector self.t[n] with n = 0 ... N_points + N_start ===
        N_user = safe_eval(self.ui.ledN_points.text(), 0, return_type='int', sign='pos')
        if N_user == 0: # automatic calculation
            self.N = self.calc_n_points(N_user)
        else:
            self.N = N_user
        
        self.N += self.ui.N_start # total number of points to be calculated: N + N_start
        self.t = np.linspace(0, self.N/fb.fil[0]['f_S'], self.N, endpoint=False)

        # calculate stimuli x[n] ==============================================
        stim = str(self.ui.cmbStimulus.currentText())
        if stim == "Pulse":
            self.x = np.zeros(self.N)
            self.x[0] = self.ui.A1 # create dirac impulse as input signal
            self.title_str = r'Impulse Response'
            self.H_str = r'$h[n]$' # default

        elif stim == "Step":
            self.x = self.ui.A1 * np.ones(self.N) # create step function
            self.title_str = r'Step Response'
            self.H_str = r'$h_{\epsilon}[n]$'
            
        elif stim == "StepErr":
            self.x = self.ui.A1 * np.ones(self.N) # create step function
            self.title_str = r'Settling Error'
            self.H_str = r'$h_{\epsilon, \infty} - h_{\epsilon}[n]$'
            
        elif stim == "Cos":
            self.x = self.ui.A1 * np.cos(2 * np.pi * self.t * self.f1)
            self.title_str = r'Transient Response to Cosine Signal'
            self.H_str = r'$y_{\cos}[n]$'
                
        elif stim == "Sine":
            self.x = self.ui.A1 * np.sin(2 * np.pi * self.t * self.f1 + self.ui.phi1) +\
                self.ui.A2 * np.sin(2 * np.pi * self.t * self.f2 + self.ui.phi2)
            self.title_str = r'Transient Response to Sinusoidal Signal'
            self.H_str = r'$y_{\sin}[n]$'
            
        elif stim == "Rect":
            self.x = self.ui.A1 * np.sign(np.sin(2 * np.pi * self.t * self.f1))
            self.title_str = r'Transient Response to Rect. Signal'
            self.H_str = r'$y_{rect}[n]$'

        elif stim == "Saw":
            self.x = self.ui.A1 * sig.sawtooth(self.t * self.f1 * 2*np.pi)
            self.title_str = r'Transient Response to Sawtooth Signal'
            self.H_str = r'$y_{saw}[n]$'

        else:
            logger.error('Unknown stimulus "{0}"'.format(stim))
            return
        
        # Add noise to stimulus
        if self.ui.noise == "gauss":
            self.x[self.ui.N_start:] += self.ui.noi * np.random.randn(self.N - self.ui.N_start)
        elif self.ui.noise == "uniform":
            self.x[self.ui.N_start:] += self.ui.noi * (np.random.rand(self.N - self.ui.N_start)-0.5)

        # Add DC to stimulus when visible / enabled
        if self.ui.ledDC.isVisible:
            self.x += self.ui.DC
        
        # calculate response self.y[n] and self.y_i[n] (for complex case) =====   
        self.bb = np.asarray(fb.fil[0]['ba'][0])
        self.aa = np.asarray(fb.fil[0]['ba'][1])
        if min(len(self.aa), len(self.bb)) < 2:
            logger.error('No proper filter coefficients: len(a), len(b) < 2 !')
            return

        sos = np.asarray(fb.fil[0]['sos'])
        antiCausal = 'zpkA' in fb.fil[0]
        causal     = not (antiCausal)

        if len(sos) > 0 and (causal): # has second order sections and is causal
            y = sig.sosfilt(sos, self.x)
        elif (antiCausal):
            y = sig.filtfilt(self.bb, self.aa, self.x, -1, None)
        else: # no second order sections or antiCausals for current filter
            y = sig.lfilter(self.bb, self.aa, self.x)



        if stim == "StepErr":
            dc = sig.freqz(self.bb, self.aa, [0]) # DC response of the system
            y = y - abs(dc[1]) # subtract DC (final) value from response

        y = np.real_if_close(y, tol = 1e3)  # tol specified in multiples of machine eps
        self.cmplx = np.any(np.iscomplex(y))
        if self.cmplx:
            self.y_i = y.imag
            self.y = y.real
        else:
            self.y = y
            self.y_i = None

#------------------------------------------------------------------------------
    def update_view(self):
        """
        place holder; should update only the limits without recalculating
        the impulse respons
        """
        self.draw_impz()

#------------------------------------------------------------------------------
    def draw(self):
        """
        Recalculate response and redraw it
        """
        if self.mplwidget.mplToolbar.enabled:
            self.calc()
            self.draw_impz()

#------------------------------------------------------------------------------
    def draw_impz(self):
        """
        (Re-)draw the figure
        """
        self.ui.lblFreqUnit1.setText(to_html(fb.fil[0]['freq_specs_unit']))
        self.ui.lblFreqUnit2.setText(to_html(fb.fil[0]['freq_specs_unit']))
        N_start = self.ui.N_start
        self.load_fs()
        self.init_axes()
        
        #================ Main Plotting Routine =========================
        if self.ui.chkMarker.isChecked():
            mkfmt_r = 'o'
            mkfmt_i = 'd'
        else:
            mkfmt_r = mkfmt_i = ' '
        if self.cmplx:           
            H_i_str = r'$\Im\{$' + self.H_str + '$\}$'
            H_str = r'$\Re\{$' + self.H_str + '$\}$'
        else:
            H_str = self.H_str

        if self.ui.chkLog.isChecked():
            #self.bottom = safe_eval(self.ui.ledLogBottom.text(), self.bottom, return_type='float')
            self.ui.ledLogBottom.setText(str(self.ui.bottom))
            H_str = r'$|$ ' + H_str + '$|$ in dB'
            y = np.maximum(20 * np.log10(abs(self.y)), self.ui.bottom)
            if self.cmplx:
                y_i = np.maximum(20 * np.log10(abs(self.y_i)), self.ui.bottom)
                H_i_str = r'$\log$ ' + H_i_str + ' in dB'
        else:
            self.ui.bottom = 0
            y = self.y
            y_i = self.y_i


        if self.ui.chkPltResp.isChecked():
            [ml, sl, bl] = self.ax_r.stem(self.t[N_start:], y[N_start:], 
                bottom=self.ui.bottom, markerfmt=mkfmt_r, label = '$y[n]$')

        if self.ui.chkPltStim.isChecked():
            stem_fmt = params['mpl_stimuli']
            [ms, ss, bs] = self.ax_r.stem(self.t[N_start:], self.x[N_start:], 
                bottom=self.ui.bottom, label = 'Stim.', **stem_fmt)
            ms.set_mfc(stem_fmt['mfc'])
            ms.set_mec(stem_fmt['mec'])
            ms.set_ms(stem_fmt['ms'])
            ms.set_alpha(stem_fmt['alpha'])
            for stem in ss:
                stem.set_linewidth(stem_fmt['lw'])
                stem.set_color(stem_fmt['mec'])
                stem.set_alpha(stem_fmt['alpha'])
            bs.set_visible(False) # invisible bottomline

        expand_lim(self.ax_r, 0.02)
        self.ax_r.set_title(self.title_str)

        if self.cmplx and self.ui.chkPltResp.isChecked():
            [ml_i, sl_i, bl_i] = self.ax_i.stem(self.t[N_start:], y_i[N_start:],
                bottom=self.ui.bottom, markerfmt=mkfmt_i, label = '$y_i[n]$')
            self.ax_i.set_xlabel(fb.fil[0]['plt_tLabel'])
            # self.ax_r.get_xaxis().set_ticklabels([]) # removes both xticklabels
            # plt.setp(ax_r.get_xticklabels(), visible=False) 
            # is shorter but imports matplotlib, set property directly instead:
            [label.set_visible(False) for label in self.ax_r.get_xticklabels()]
            self.ax_r.set_ylabel(H_str + r'$\rightarrow $')
            self.ax_i.set_ylabel(H_i_str + r'$\rightarrow $')
        else:
            self.ax_r.set_xlabel(fb.fil[0]['plt_tLabel'])
            self.ax_r.set_ylabel(H_str + r'$\rightarrow $')


        if self.ACTIVE_3D: # not implemented / tested yet
            # plotting the stems
            for i in range(N_start, self.self.N):
              self.ax3d.plot([self.t[i], self.t[i]], [y[i], y[i]], [0, y_i[i]],
                             '-', linewidth=2, alpha=.5)

            # plotting a circle on the top of each stem
            self.ax3d.plot(self.t[N_start:], y[N_start:], y_i[N_start:], 'o', markersize=8,
                           markerfacecolor='none', label='$y[n]$')

            self.ax3d.set_xlabel('x')
            self.ax3d.set_ylabel('y')
            self.ax3d.set_zlabel('z')

        self.redraw()

#------------------------------------------------------------------------------
    def redraw(self):
        """
        Redraw the canvas when e.g. the canvas size has changed
        """
        self.mplwidget.redraw()

#------------------------------------------------------------------------------        
    def calc_n_points(self, N_user = 0):
        """
        Calculate number of points to be displayed, depending on type of filter 
        (FIR, IIR) and user input. If the user selects 0 points, the number is
        calculated automatically.
        
        An improvement would be to calculate the dominant pole and the corresponding
        settling time.
        """

        if N_user == 0: # set number of data points automatically
            if fb.fil[0]['ft'] == 'IIR':
                N = 100
            else:
                N = min(len(fb.fil[0]['ba'][0]),  100) # FIR: N = number of coefficients (max. 100)
        else:
            N = N_user

        return N

#------------------------------------------------------------------------------

def main():
    import sys
    from ..compat import QApplication

    app = QApplication(sys.argv)
    mainw = PlotImpz(None)
    app.setActiveWindow(mainw) 
    mainw.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

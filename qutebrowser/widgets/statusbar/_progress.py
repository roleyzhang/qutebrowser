# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""The progress bar in the statusbar."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QProgressBar, QSizePolicy

from qutebrowser.config.style import set_register_stylesheet


class Progress(QProgressBar):

    """The progress bar part of the status bar.

    Class attributes:
        STYLESHEET: The stylesheet template.
    """

    # FIXME for some reason, margin-left is not shown
    STYLESHEET = """
        QProgressBar {{
            border-radius: 0px;
            border: 2px solid transparent;
            margin-left: 1px;
            background-color: transparent;
        }}

        QProgressBar::chunk {{
            {color[statusbar.progress.bg]}
        }}
    """

    def __init__(self, parent):
        super().__init__(parent)
        set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self.setTextVisible(False)
        self.hide()

    @pyqtSlot()
    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.setValue(0)
        self.show()
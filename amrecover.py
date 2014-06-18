#!/usr/bin/python3.3
# -*- coding: utf-8 -*-
'''
Created on 2014-06-14 19:17
@summary: 
@author: i.melentsov
'''

import sys
import os
import datetime
import json
import argparse

from PyQt5.QtCore import (QSize, Qt, QDir, QItemSelectionModel )
from PyQt5.QtWidgets import (QApplication, QFileSystemModel, QTreeView, QHeaderView,
 QMainWindow, QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QLabel, QFrame, QTextEdit, QPushButton)
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QTextCursor
from PyQt5 import QtWidgets

from amrecover_core import AmrecoverWrapper

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.resize(QSize(870, 550))
        self.setCentralWidget(MainWidget(self))


class MainWidget(QWidget):
    def __init__(self, ma):
        super(MainWidget, self).__init__()
        self.ma = ma

        mainLayout = QVBoxLayout()

        splitter = QSplitter()
        self.local_path_view = LocalPathView()
        self.server_path_view = ServerPathView()
        splitter.addWidget(self.server_path_view)
        splitter.addWidget(self.local_path_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self.command_output = QTextEdit()
        self.command_output.setReadOnly(True)

        splitter_vl = QSplitter()
        splitter_vl.setOrientation(Qt.Vertical)
        splitter_vl.addWidget(splitter)
        splitter_vl.addWidget(self.command_output)
        splitter_vl.setStretchFactor(0, 8)
        splitter_vl.setStretchFactor(1, 2)
        

        command_line_hl = QHBoxLayout()
        fcommand_line_name = QLabel("Command line:")
        self.lineEdit = QLineEdit()
        extract_button = QPushButton("Extract") 
        command_line_hl.addWidget(fcommand_line_name)
        command_line_hl.addWidget(self.lineEdit)
        command_line_hl.addWidget(extract_button)

        mainLayout.addWidget(splitter_vl)
        mainLayout.addLayout(command_line_hl)
        
        self.setLayout(mainLayout)

        self.lineEdit.returnPressed.connect(self.processCommand)
        extract_button.clicked.connect(self.extract)

        config = {}
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
        except :
            pass
        # [--version] [[-C] <config>] [-s <index-server>] [-t <tape-server>] [-d <tape-device>] [-o <clientconfigoption>]*
        prog_name = sys.argv[0]
        parser = argparse.ArgumentParser()
        if len(sys.argv) > 1:
            if(sys.argv[1] == "-C"):
                sys.argv.pop(1)
            if (sys.argv[1][0] != '-'):
                config['config'] = sys.argv[1]
                sys.argv.pop(1)
        parser.add_argument("-s", dest='index_server')
        parser.add_argument("-t", dest='tape_server')
        parser.add_argument("-d", dest='tape_device')
        parser.add_argument('args', nargs=argparse.REMAINDER)
        parsed = parser.parse_args()
        if parsed.index_server:
            config['index_server'] = parsed.index_server
        if parsed.tape_server:
            config['tape_server'] = parsed.tape_server
        if parsed.tape_device:
            config['tape_device'] = parsed.tape_device
        config["args"] = parsed.args
        sys.argv = [prog_name]

        self.amrecover = AmrecoverWrapper(config)
        self.command_output.setPlainText(self.amrecover.getCommandRes())

    def processCommand(self):
        command = self.lineEdit.text().strip()
        self.lineEdit.setText('') 
        if(command == 'quit' or command == 'exit'):
            self.amrecover.quit()
            self._append_text_to_command_output(self.amrecover.getCommandRes())
            self.ma.close()
        elif(command == 'extract'):
            self.extract()
        elif(len(command) > 6 and command[:7] == 'setdisk'):
            self.amrecover.command(command + '\n')
            res = self.amrecover.getCommandRes()
            self._append_text_to_command_output(res)
            if res.split('\n')[1].startswith('200'):
                self.server_path_view.updateTree(self.amrecover.getPathTree())
        else:
            self.amrecover.command(command + '\n')
            self._append_text_to_command_output(self.amrecover.getCommandRes())

    def _append_text_to_command_output(self, text):
        self.command_output.moveCursor(QTextCursor.End)
        self.command_output.insertPlainText(text)
        self.command_output.moveCursor(QTextCursor.End)

    def extract(self):
        self.amrecover.command("lcd " + self.local_path_view.selectedDir + '\n')
        self._append_text_to_command_output(self.amrecover.getCommandRes())

        restoring = self.server_path_view.getChecked()
        for date in sorted(restoring):
            if restoring[date]:
                self.amrecover.command("setdate " + date + '\n')
                self._append_text_to_command_output(self.amrecover.getCommandRes())
                for path in restoring[date]:
                    self.amrecover.command("add " + (path + '.' if path.endswith('/') else path) + '\n')
                    self._append_text_to_command_output(self.amrecover.getCommandRes())
        cur_date = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.amrecover.command("setdate " + cur_date + '\n')
        self._append_text_to_command_output(self.amrecover.getCommandRes())
        self.amrecover.command("extract\n")
        self._append_text_to_command_output(self.amrecover.getCommandRes())


class LocalPathView(QTreeView):
    def __init__ (self):
        super(LocalPathView, self).__init__()
        self._model = QFileSystemModel()
        self._model.setFilter(QDir.Dirs | QDir.Drives | QDir.NoDotAndDotDot | QDir.AllDirs)
        self._model.setRootPath('')
        self.setModel(self._model )

        self.hideColumn(1); # removing Size Column
        self.hideColumn(2); # removing Type Column
        self.setAnimated(False)
        self.setSortingEnabled(True)
        self.header().setSortIndicator(0, Qt.AscendingOrder)

        width = self.size().width() >> 1
        self.setColumnWidth(0, width*0.7)
        self.setColumnWidth(1, width*0.3)

        index = self._model.index(QDir.currentPath())
        self.selectionModel().setCurrentIndex(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.expand(index)
        self.scrollTo(index)

    @property
    def selectedDir(self):
        return self._model.filePath(self.selectionModel().selectedIndexes()[0])



class TreeModel(QStandardItemModel):
    """ model for ServerPathView """

    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsUserCheckable | Qt.ItemIsEnabled

    def getCheckedPathItems(self):
        res = {}
        root_index = self.indexFromItem(self.invisibleRootItem())
        rows = self.rowCount(root_index)
        for row in range(0,rows): # walking by dates
            index = self.index(row, 0, root_index)
            selected_date = self.data(index)[:19]
            res_by_date = []
            cur_root_index = self.index(0, 0, index)
            indexes = [cur_root_index]
            dirs_from_root = [self.data(cur_root_index)]

            if self.itemFromIndex(cur_root_index).checkState():
                res_by_date.append(dirs_from_root[0] + '/')
                self.itemFromIndex(cur_root_index).setCheckState(Qt.Unchecked)

            while indexes:
                cur_root_index = indexes.pop() # deeper
                dir_from_root = dirs_from_root.pop()
                rows = self.rowCount(cur_root_index)
                for _row in range(0,rows):
                    index = self.index(_row, 0, cur_root_index)
                    indexes.append(index)
                    full_path = dir_from_root + '/' + self.data(index) + ( '/' if self.rowCount(index) else '')
                    dirs_from_root.append(full_path)
                    if self.itemFromIndex(index).checkState():
                        self.itemFromIndex(index).setCheckState(Qt.Unchecked)
                        res_by_date.append(full_path)
            res[selected_date] = res_by_date
        return res

class ServerPathView(QTreeView):
    def __init__ (self):
        super(ServerPathView, self).__init__()
        self.model = TreeModel()
        self.model.setHorizontalHeaderLabels(('Name',))
        self.setModel(self.model)

    def updateTree(self, root_item):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(('Name',))
        parentItem = self.model.invisibleRootItem()

        for date_item in root_item.children:
            item = QStandardItem(date_item.data)
            parentItem.appendRow(item)
            items = [item]
            childrenS = [date_item.children]
            while items:
                cur_parent_item = items.pop()
                his_children = childrenS.pop()
                for child in his_children:
                    item = QStandardItem(child.data)
                    item.setCheckable(True)
                    cur_parent_item.appendRow(item)
                    if child.has_children:
                        items.append(item)
                        childrenS.append(child.children)

    def getChecked(self):
        return self.model.getCheckedPathItems()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('./images/icon.ico'))
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
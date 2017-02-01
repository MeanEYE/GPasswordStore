#!/usr/bin/env python
#
#	Gnome Password Store
#	Copyright (c) 2017. by Mladen (MeanEYE) Mijatov
#
#	This program was made to provide easy way of searching and copying
#	passwords in Gnome Shell running on Wayland. However program was done
#	in such a way to provide as much flexibility with desktop envorinment
#	as possible.
#
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
import os
import subprocess

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib


class Column:
	PATH = 0
	SEARCH = 1


class GPasswordStore(Gtk.Application):
	"""Simple password store application."""
	TITLE = 'Password Store'

	def __init__(self):
		Gtk.Application.__init__(self)

	def do_activate(self):
		"""Initialize application."""
		GLib.set_application_name(self.TITLE)

		# create main window
		main_window = MainWindow(self)
		self.add_window(main_window)

		# show main window
		main_window.show_all()

	def do_startup(self):
		"""Start application up."""
		Gtk.Application.do_startup(self)


class MainWindow(Gtk.ApplicationWindow):
	"""Main application window which copies passwords to clipboard."""
	TIMEOUT = 30

	def __init__(self, application):
		Gtk.ApplicationWindow.__init__(self, application=application)

		self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

		# configure window
		self.set_default_size(400, 300)
		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_default_icon_name('password')
		self.set_wmclass(GPasswordStore.TITLE, GPasswordStore.TITLE)
		self.set_title(GPasswordStore.TITLE)

		# create header bar
		header_bar = Gtk.HeaderBar.new()
		header_bar.set_show_close_button(False)
		header_bar.set_title(GPasswordStore.TITLE)
		self.set_titlebar(header_bar)

		# create search entry
		self._entry = Gtk.Entry.new()
		header_bar.set_custom_title(self._entry)

		self._entry.grab_focus()
		self._entry.connect('key-press-event', self.__handle_entry_key_press)

		# create item list
		scrolled_window = Gtk.ScrolledWindow()
		scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
		self._store = Gtk.ListStore.new((str, str))
		self._list = Gtk.TreeView.new_with_model(self._store)

		self._list.set_headers_visible(False)
		self._list.set_activate_on_single_click(True)
		self._list.set_search_entry(self._entry)
		self._list.set_search_equal_func(self.__search_compare)
		self._list.connect('focus-in-event', self.__handle_list_focus)
		self._list.connect('row-activated', self.__handle_list_row_activated)

		scrolled_window.add(self._list)
		self.add(scrolled_window)

		# create cell renders
		cell_text = Gtk.CellRendererText.new()

		# create columns
		column_path = Gtk.TreeViewColumn.new()
		column_path.pack_start(cell_text, True)
		column_path.add_attribute(cell_text, 'text', Column.PATH)
		self._list.append_column(column_path)

		# populate data
		self.__populate_data()

		# highlight first item
		first_iter = self._store.get_iter_first()
		self._list.set_cursor(self._store.get_path(first_iter))

	def __populate_data(self):
		"""Populate list data."""
		# get directory to traverse
		if 'PASSWORD_STORE_DIR' in os.environ:
			directory = os.path.expanduser(os.environ['PASSWORD_STORE_DIR'])
			if directory.endswith('/'):
				directory = directory[:-1]

		else:
			directory = os.path.expanduser('~/.password-store')

		# traverse directory and populate list
		for path, found_dirs, found_files in os.walk(directory):
			# we are searching for files
			if len(found_files) == 0:
				continue

			# check if path is not part of hidden directory
			relative_path = path[len(directory)+1:]
			if relative_path.startswith('.'):
				continue

			# add found files
			for file_name in found_files:
				if not file_name.endswith('.gpg'):
					continue

				full_path = os.path.join(relative_path, file_name)[:-4]
				self._store.append((full_path, full_path.lower()))

	def __search_compare(self, model, column, key, current_iter):
		"""Comparison function for quick search."""
		path = model.get_value(current_iter, Column.SEARCH)
		words = key.lower().split()
		matches = map(lambda word: word in path, words)

		return sum(matches) != len(words)

	def __handle_list_focus(self, widget, data=None):
		"""Handle list gaining focus."""
		self._entry.grab_focus()

	def __handle_list_row_activated(self, widget, path, data=None):
		"""Handle row activation through keystroke or mouse click."""
		self.get_selected_password()
		return True

	def __handle_entry_key_press(self, widget, event, data=None):
		"""Handle specific key presses."""
		result = False

		# handle up and down navigation
		if event.keyval == Gdk.KEY_Down or event.keyval == Gdk.KEY_Up:
			selected_iter = self._store.get_iter(self._list.get_cursor()[0])

			if event.keyval == Gdk.KEY_Down:
				next_iter = self._store.iter_next(selected_iter)
			else:
				next_iter = self._store.iter_previous(selected_iter)

			if next_iter is not None:
				path = self._store.get_path(next_iter)
				self._list.set_cursor(path)
				self._list.scroll_to_cell(path)

			result = True

		# handle selecting password with keyboard
		elif event.keyval == Gdk.KEY_Return:
			self.get_selected_password()
			result = True

		# handle easy way to close applicaiton with escape
		elif event.keyval == Gdk.KEY_Escape:
			self.destroy()
			result = True

		return result

	def __handle_timeout(self):
		"""Clear clipboard and close application."""
		self._clipboard.set_text('', -1)
		self.destroy()

		return False

	def get_selected_password(self):
		"""Unlock and copy selected password."""
		# prepare data for password store
		selected_iter = self._store.get_iter(self._list.get_cursor()[0])
		selected_path = self._store.get_value(selected_iter, Column.PATH)

		# communicate with password store through pipe
		environment = os.environ.copy()
		output = subprocess.Popen(
							('pass', selected_path),
							env=environment,
							stdout=subprocess.PIPE
						).communicate()

		# copy password to clipboard
		password = output[0].split('\n')[0]
		self._clipboard.set_text(password, -1)

		# schedule autodestruct
		GLib.timeout_add_seconds(self.TIMEOUT, self.__handle_timeout)

		# close window immediately
		self.hide()


if __name__ == '__main__':
	application = GPasswordStore()
	application.run()

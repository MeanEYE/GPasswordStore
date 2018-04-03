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
	NAME = 0
	PATH = 1
	SEARCH = 2
	ICON = 3
	IS_DIRECTORY = 4


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
	TIMEOUT = 45

	def __init__(self, application):
		Gtk.ApplicationWindow.__init__(self, application=application)

		self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		self._iter_referrence = {}

		# configure window
		self.set_default_size(400, 500)
		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_default_icon_name('password')
		self.set_wmclass(GPasswordStore.TITLE, GPasswordStore.TITLE)
		self.set_title(GPasswordStore.TITLE)

		# create header bar
		header_bar = Gtk.HeaderBar.new()
		header_bar.set_show_close_button(True)
		header_bar.set_title(GPasswordStore.TITLE)
		self.set_titlebar(header_bar)

		# create button box
		button_new = Gtk.Button.new_from_icon_name('add', Gtk.IconSize.BUTTON)
		header_bar.pack_start(button_new)

		# window widget container
		box = Gtk.VBox.new(False, 0)
		self.add(box)

		# create search entry
		self._entry = Gtk.SearchEntry.new()
		self._entry.grab_focus()
		self._entry.connect('key-press-event', self.__handle_entry_key_press)

		search_bar = Gtk.SearchBar.new()
		search_bar.set_search_mode(True)
		search_bar.add(self._entry)
		search_bar.connect_entry(self._entry)
		box.pack_start(search_bar, False, False, 0)

		# create item list
		scrolled_window = Gtk.ScrolledWindow()
		scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
		self._store = Gtk.TreeStore.new((str, str, str, str, bool))
		self._list = Gtk.TreeView.new_with_model(self._store)

		self._list.set_headers_visible(False)
		self._list.set_activate_on_single_click(True)
		self._list.set_search_entry(self._entry)
		self._list.set_search_equal_func(self.__search_compare)
		self._list.connect('focus-in-event', self.__handle_list_focus)
		self._list.connect('row-activated', self.__handle_list_row_activated)

		scrolled_window.add(self._list)
		box.pack_start(scrolled_window, True, True, 0)

		# create cell renders
		cell_icon = Gtk.CellRendererPixbuf.new()
		cell_text = Gtk.CellRendererText.new()
		cell_text.set_padding(5, 5)

		# create columns
		column_path = Gtk.TreeViewColumn.new()
		column_path.pack_start(cell_icon, False)
		column_path.pack_start(cell_text, True)

		column_path.add_attribute(cell_icon, 'icon_name', Column.ICON)
		column_path.add_attribute(cell_text, 'text', Column.NAME)

		column_path.set_sort_column_id(Column.PATH)
		self._list.append_column(column_path)

		# populate data
		self.__populate_data()
		self._list.expand_all()

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

			# get parent iter for tree storage
			parent_iter = self.__get_parent_iter(relative_path)

			# add found files
			for file_name in found_files:
				if not file_name.endswith('.gpg'):
					continue

				full_path = os.path.join(relative_path, file_name)[:-4]
				self._store.append(parent_iter, (
						os.path.basename(full_path),
						full_path,
						full_path.lower(),
						'application-pgp-keys',
						False
					))

	def __get_parent_iter(self, path):
		"""Get parent iter for specified path.

		If iter doesn't exist system will create every missing parent
		iter in the link creating a proper structure.

		"""
		path_elements = path.split(os.sep)

		# account for root elements
		if path == '':
			return None

		# create path fragments
		current_path = ''
		for element in path_elements:
			parent_path = current_path
			current_path = os.path.join(current_path, element)

			if element[0] == '.':
				return None

			# path fragment wasn't found in referrence dictionary
			if current_path not in self._iter_referrence:
				if parent_path != '':
					parent_iter = self._iter_referrence[parent_path]
				else:
					parent_iter = None

				self._iter_referrence[current_path] = self._store.append(parent_iter, (
						element,
						current_path,
						current_path.lower(),
						'folder',
						True
					))

		return self._iter_referrence[path]

	def __search_compare(self, model, column, key, current_iter):
		"""Comparison function for quick search."""
		path = model.get_value(current_iter, Column.SEARCH)
		is_directory = model.get_value(current_iter, Column.IS_DIRECTORY)

		# match words
		words = key.lower().split()
		matches = map(lambda word: word in path, words)

		return is_directory or sum(matches) != len(words)

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

		# make sure we are not trying to get password from directory node
		if self._store.get_value(selected_iter, Column.IS_DIRECTORY):
			return

		# communicate with password store through pipe
		environment = os.environ.copy()
		output, errors = subprocess.Popen(
							('pass', selected_path),
							env=environment,
							stdout=subprocess.PIPE,
							stderr=subprocess.PIPE
						).communicate()

		# show error message
		if (len(errors) > 0):
			message = Gtk.MessageDialog(
						self,
						Gtk.DialogFlags.DESTROY_WITH_PARENT,
						Gtk.MessageType.ERROR,
						Gtk.ButtonsType.OK,
						'The following error(s) occurred:\n{}'.format(errors)
					)
			message.run()
			message.destroy()
			return

		# copy password to clipboard
		password = output.split('\n')[0]
		self._clipboard.set_text(password, -1)

		# schedule auto-destruct
		GLib.timeout_add_seconds(self.TIMEOUT, self.__handle_timeout)

		# close window immediately
		self.hide()


if __name__ == '__main__':
	application = GPasswordStore()
	application.run()

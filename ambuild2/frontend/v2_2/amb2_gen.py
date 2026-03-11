# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
import os
from ambuild2 import util
from ambuild2.frontend import amb2_gen
from ambuild2.frontend.v2_2.cpp import builders
from ambuild2.frontend.v2_2.cpp import detect
from ambuild2.frontend.v2_2.cpp import export_cmake

class Generator(amb2_gen.Generator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.cmake = export_cmake.Exporter(cm)
        self.cmake_file_ops = {}

    def postGenerate(self):
        super(Generator, self).postGenerate()
        if getattr(self.cm.options, 'generate_cmake', False):
            self.cmake.write()

    def detectCompilers(self, **kwargs):
        with util.FolderChanger(self.cacheFolder):
            return detect.AutoDetectCxx(self.cm.host, self.cm.options, **kwargs)

    def addCMakeTarget(self, builder):
        self.cmake.add_target(builder)

    def addCopy(self, context, source, output_path):
        result = super(Generator, self).addCopy(context, source, output_path)
        self._record_file_op(context, source, result[1][0], 'copy')
        return result

    def addSymlink(self, context, source, output_path):
        result = super(Generator, self).addSymlink(context, source, output_path)
        self._record_file_op(context, source, result[1][0], 'symlink')
        return result

    def _record_file_op(self, context, source, output_entry, kind):
        if not getattr(self.cm.options, 'generate_cmake', False):
            return

        source_path = self._resolve_file_op_path(context, source)
        output_path = self._resolve_file_op_path(None, output_entry)
        self.cmake_file_ops[output_path] = {
            'kind': kind,
            'source': source_path,
            'output': output_path,
        }

    def _resolve_file_op_path(self, context, value):
        if hasattr(value, 'path'):
            path = value.path
            if not os.path.isabs(path):
                path = os.path.join(self.cm.buildPath, path)
            return os.path.normpath(path)

        if not os.path.isabs(value) and context is not None:
            value = os.path.join(context.currentSourcePath, value)
        return os.path.normpath(value)

    def newProgramProject(self, context, name):
        return builders.Project(builders.Program, name)

    def newLibraryProject(self, context, name):
        return builders.Project(builders.Library, name)

    def newStaticLibraryProject(self, context, name):
        return builders.Project(builders.StaticLibrary, name)

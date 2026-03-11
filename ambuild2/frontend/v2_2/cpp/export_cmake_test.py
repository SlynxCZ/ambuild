import os
import unittest

from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.cpp import builders
from ambuild2.frontend.v2_2.cpp import export_cmake
from ambuild2.frontend.v2_2.cpp.compiler import CliCompiler
from ambuild2.frontend.v2_2.cpp.gcc import GCC


class FakeContext(object):
    def __init__(self, current_source_path, source_folder = '', build_folder = '', build_path = None):
        self.currentSourcePath = current_source_path
        self.sourceFolder = source_folder
        self.buildFolder = build_folder
        self.buildPath = build_path


class FakeNode(object):
    def __init__(self, path):
        self.path = path


class FakeCm(object):
    def __init__(self, source_path, build_path):
        self.sourcePath = source_path
        self.buildPath = build_path
        self.generator = type('Generator', (), {'cmake_file_ops': {}})()


class FakeProtoc(object):
    def __init__(self, path = '/usr/bin/protoc'):
        self.path = path
        self.extra_argv = []
        self.includes = []


class FakeProtocJob(object):
    def __init__(self, protoc, sources):
        self.protoc = protoc
        self.sources = sources


class ExportCMakeTest(unittest.TestCase):
    def test_binary_builder_renders_cmake_target(self):
        cm = FakeCm('C:/src/project', 'C:/src/project/objdir')
        compiler = CliCompiler(GCC('13.2'), System('linux', 'x86_64'), ['cc'], ['c++'])
        compiler.includes += ['include', '/opt/sdk/include']
        compiler.cxxincludes += ['cxx/include']
        compiler.defines += ['DEBUG']
        compiler.cxxdefines += ['FEATURE=1']
        compiler.cflags += ['-Wall']
        compiler.cxxflags += ['-std=c++20']
        compiler.linkflags += ['-pthread', '-L/opt/sdk/lib']
        compiler.postlink += [FakeNode('generated/helper.lib')]

        builder = builders.Program(compiler, 'sample')
        root = builders.Module(FakeContext('C:/src/project/src'), compiler, 'root')
        root.sources = ['main.cpp', FakeNode('generated/file.cpp')]
        builder.modules_ = [root]

        exporter = export_cmake.Exporter(cm)
        exporter.add_target(builder)
        rendered = exporter.render()

        self.assertIn('add_executable(sample', rendered)
        self.assertIn('"C:/src/project/src/main.cpp"', rendered)
        self.assertIn('"C:/src/project/objdir/generated/file.cpp"', rendered)
        self.assertIn('target_include_directories(sample PRIVATE', rendered)
        self.assertIn('"include"', rendered)
        self.assertIn('target_compile_definitions(sample PRIVATE', rendered)
        self.assertIn('"FEATURE=1"', rendered)
        self.assertIn('target_compile_options(sample PRIVATE', rendered)
        self.assertIn('"-std=c++20"', rendered)
        self.assertIn('target_link_directories(sample PRIVATE', rendered)
        self.assertIn('"/opt/sdk/lib"', rendered)
        self.assertIn('target_link_options(sample PRIVATE', rendered)
        self.assertIn('"-pthread"', rendered)
        self.assertIn('target_link_libraries(sample PRIVATE', rendered)
        self.assertIn('"C:/src/project/objdir/generated/helper.lib"', rendered)

    def test_package_copy_copies_binary_and_vdf(self):
        cm = FakeCm('/src/project', '/build/project')
        compiler = CliCompiler(GCC('13.2'), System('linux', 'x86_64'), ['cc'], ['c++'])

        target_output = os.path.normpath('/build/project/client_cvar_value/linux-x86_64/client_cvar_value.dll')
        bundled_output = os.path.normpath('/build/project/package/addons/client_cvar_value/client_cvar_value.dll')
        vdf_source = os.path.normpath('/build/project/client_cvar_value.vdf')
        vdf_output = os.path.normpath('/build/project/package/addons/metamod/client_cvar_value.vdf')
        cm.generator.cmake_file_ops[bundled_output] = {
            'kind': 'copy',
            'source': target_output,
            'output': bundled_output,
        }
        cm.generator.cmake_file_ops[vdf_output] = {
            'kind': 'copy',
            'source': vdf_source,
            'output': vdf_output,
        }

        builder = builders.Library(compiler, 'client_cvar_value')
        builder.modules_ = [builders.Module(FakeContext('/src/project'), compiler, 'root')]

        exporter = export_cmake.Exporter(cm)
        exporter.add_target(builder)
        rendered = exporter.render()

        self.assertIn('add_custom_command(TARGET client_cvar_value POST_BUILD', rendered)
        self.assertIn('"$<TARGET_FILE:client_cvar_value>"', rendered)
        self.assertIn('"/build/project/package/addons/client_cvar_value/client_cvar_value.dll"', rendered)
        self.assertIn('"/build/project/client_cvar_value.vdf"', rendered)
        self.assertIn('"/build/project/package/addons/metamod/client_cvar_value.vdf"', rendered)
        self.assertNotIn('"/home/hl2sdk-cs2/lib/linux64/libtier0.so"', rendered)

    def test_synthetic_link_input_uses_original_library_path(self):
        cm = FakeCm('/src/project', '/build/project')
        compiler = CliCompiler(GCC('13.2'), System('linux', 'x86_64'), ['cc'], ['c++'])
        compiler.linkflags += ['libtier0.so']
        compiler.weaklinkdeps += [FakeNode('client_cvar_value/linux-x86_64/libtier0.so')]
        cm.generator.cmake_file_ops[os.path.normpath('/build/project/client_cvar_value/linux-x86_64/libtier0.so')] = {
            'kind': 'symlink',
            'source': '/home/hl2sdk-cs2/lib/linux64/libtier0.so',
            'output': '/build/project/client_cvar_value/linux-x86_64/libtier0.so',
        }

        builder = builders.Library(compiler, 'client_cvar_value')
        builder.modules_ = [builders.Module(FakeContext('/src/project'), compiler, 'root')]

        exporter = export_cmake.Exporter(cm)
        exporter.add_target(builder)
        rendered = exporter.render()

        self.assertIn('target_link_libraries(client_cvar_value PRIVATE', rendered)
        self.assertIn('"/home/hl2sdk-cs2/lib/linux64/libtier0.so"', rendered)
        self.assertNotIn('"libtier0.so"', rendered)

    def test_duplicate_names_get_target_suffix(self):
        cm = FakeCm('C:/src/project', 'C:/src/project/objdir')
        exporter = export_cmake.Exporter(cm)

        compiler_a = CliCompiler(GCC('13.2'), System('linux', 'x86'), ['cc'], ['c++'])
        builder_a = builders.Program(compiler_a, 'sample')
        builder_a.modules_ = [builders.Module(FakeContext('C:/src/project/src'), compiler_a, 'root')]

        compiler_b = CliCompiler(GCC('13.2'), System('linux', 'x86_64'), ['cc'], ['c++'])
        builder_b = builders.Program(compiler_b, 'sample')
        builder_b.modules_ = [builders.Module(FakeContext('C:/src/project/src'), compiler_b, 'root')]

        exporter.add_target(builder_a)
        exporter.add_target(builder_b)
        rendered = exporter.render()

        self.assertIn('add_executable(sample', rendered)
        self.assertIn('add_executable(sample_linux_x86_64', rendered)
        self.assertIn('set_target_properties(sample_linux_x86_64 PROPERTIES OUTPUT_NAME "sample")',
                      rendered)

    def test_protoc_custom_command_is_emitted(self):
        cm = FakeCm('/src/project', '/build/project')
        compiler = CliCompiler(GCC('13.2'), System('linux', 'x86_64'), ['cc'], ['c++'])

        builder = builders.Library(compiler, 'client_cvar_value')
        root_context = FakeContext('/src/project', '', '', '/build/project')
        module_context = FakeContext('/src/project/proto', 'proto', '', '/build/project')
        root = builders.Module(root_context, compiler, 'root')
        module = builders.Module(module_context, compiler, 'network')
        module.custom = [FakeProtocJob(FakeProtoc('/usr/bin/protoc'), ['network_connection.proto'])]
        module.sources = ['/build/project/client_cvar_value/linux-x86_64/proto/network_connection.pb.cc']
        builder.modules_ = [root, module]

        exporter = export_cmake.Exporter(cm)
        exporter.add_target(builder)
        rendered = exporter.render()

        self.assertIn('add_custom_command(', rendered)
        self.assertIn('"${CMAKE_COMMAND}"', rendered)
        self.assertIn('"make_directory"', rendered)
        self.assertIn('"/build/project/client_cvar_value/linux-x86_64/proto"', rendered)
        self.assertIn('"/usr/bin/protoc"', rendered)
        self.assertIn('"--cpp_out=/build/project/client_cvar_value/linux-x86_64/proto"', rendered)
        self.assertIn('"/src/project/proto/network_connection.proto"', rendered)
        self.assertIn('"/build/project/client_cvar_value/linux-x86_64/proto/network_connection.pb.cc"', rendered)
        self.assertIn('target_include_directories(client_cvar_value PRIVATE', rendered)
        self.assertIn('"/build/project/client_cvar_value/linux-x86_64/proto"', rendered)


if __name__ == '__main__':
    unittest.main()

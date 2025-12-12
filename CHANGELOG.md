## v0.5.0 (2025-12-12)

## v0.4.2 (2025-11-18)

### Feat

- loosen up pybind11 requirements to <3.0

## v0.4.1 (2025-11-17)

### Feat

- BuildPybind11Extension gained extra linking_library_search_paths option

### Fix

- iter_otool_lib_dependencies can handle shared libraries that use the .so extension

## v0.4.0 (2025-09-29)

### Fix

- workaround for building python extensions with runtime_library_dirs on windows

### Refactor

- use actual src file for tests. fixes missing json file on windows
- use actual src file for tests. fixes sonar from thinking it needs to check cpp code
- use actual src file for tests. fixes missing json file
- use actual src file for tests

## v0.3.0 (2025-09-29)

### Fix

- workaround for building python extensions with runtime_library_dirs on windows

### Refactor

- use actual src file for tests. fixes missing json file on windows
- use actual src file for tests. fixes sonar from thinking it needs to check cpp code
- use actual src file for tests. fixes missing json file
- use actual src file for tests

## v0.2.9 (2025-08-08)

## v0.2.7 (2025-08-04)

### Feat

- compiler definitions can now handle definitions with assignment
- more system dlls identified.

### Fix

- recognize more Windows system libraries

## v0.2.6 (2025-07-24)

### Feat

- if creating a new settings.yml from conan, add current compiler version it

### Fix

- issue don't know how to compile C/C++ code on platform 'posix'

### Refactor

- moved set_env_var to uiucprescon.build.utils
- broke up fix_up_darwin_libraries
- move source code in src directory

## v0.2.5 (2025-04-24)

## v0.2.3 (2024-11-05)

## v0.2.2 (2024-11-04)

## v0.2.1 (2024-09-04)

## v0.1.2 (2023-03-06)

## v0.1.0 (2022-12-16)

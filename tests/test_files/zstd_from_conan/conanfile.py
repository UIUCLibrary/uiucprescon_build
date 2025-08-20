from conan import ConanFile


class Dummy(ConanFile):
    requires = ["zstd/1.5.7"]
    default_options = {"zstd/*:shared": True}

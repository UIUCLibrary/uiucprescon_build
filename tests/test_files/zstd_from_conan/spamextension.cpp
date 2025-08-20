#include <iostream>
#include "zstd.h"
#include <pybind11/pybind11.h>
const std::string get_version(){
    return ZSTD_versionString();
}
PYBIND11_MODULE(spam, m){
    m.doc() = R"pbdoc(Spam lovely spam)pbdoc";
    m.def("get_version", &get_version, "Get the version of lib linked to");
}

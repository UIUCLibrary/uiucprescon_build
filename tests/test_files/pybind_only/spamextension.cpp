#include <iostream>
#include <pybind11/pybind11.h>
PYBIND11_MODULE(spam, m){
    m.doc() = R"pbdoc(Spam lovely spam)pbdoc";
}

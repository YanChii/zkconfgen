#!/bin/sh
# run in the zkconfgen.git directory
#./build_rpm.sh

rpmbuild -v -bb --define "_sourcedir $(pwd)" zkconfgen.spec

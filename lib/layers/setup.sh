#!/bin/bash

for case in stripe
do
    rm ${case}_layer.zip 
    mkdir -p layer/python/lib/python3.11/site-packages/
    python3.11 -m pip install -r ${case}_requirements.txt -t layer/python/lib/python3.11/site-packages/
    pushd layer
        zip -r9 ../${case}_layer.zip .
    popd
    rm -rf layer
done
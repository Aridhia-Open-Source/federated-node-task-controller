#!/bin/bash

make build_helper
microk8s ctr images rm ghcr.io/aridhia-open-source/fn_task_controller_helper:1.0.0
docker save ghcr.io/aridhia-open-source/fn_task_controller_helper:1.0.0 > fn.tar
microk8s ctr image import fn.tar
rm fn.tar

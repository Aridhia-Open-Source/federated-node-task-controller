SHELL=/bin/bash
IMAGE ?= custom_controller:0.0.1

build:
	docker build . -t "${IMAGE}"

send_micro: build
	docker save "${IMAGE}" > fndev.tar
	microk8s ctr image import fndev.tar
	rm fndev.tar

restart_controller:
	kubectl rollout restart -n controller deployment analytics-operator

apply:
	kubectl apply -f k8s/

exec_docker:
	docker run --rm -it --entrypoint sh ${IMAGE}

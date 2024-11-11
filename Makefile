SHELL=/bin/bash
IMAGE ?= ghcr.io/aridhia-open-source/fn_task_controller:0.0.1-dev
TESTS_IMAGE ?= ghcr.io/aridhia-open-source/fn_task_controller_tests
TEST_CONTAINER ?= fn-controller-tests

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

tests_local:
	pytest -v --cov-report xml:artifacts/coverage.xml --cov=controller

tests_ci:
	docker build . -f test.Dockerfile -t ${TESTS_IMAGE}
	docker run --name ${TEST_CONTAINER} ${TESTS_IMAGE}
	docker cp ${TEST_CONTAINER}:/app/controller/artifacts/coverage.xml artifacts/coverage.xml
	docker rm ${TEST_CONTAINER}

pylint_ci:
	./scripts/linting/pylint.sh

hadolint:
	./scripts/tests/hadolint.sh

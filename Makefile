SHELL=/bin/bash
IMAGE ?= ghcr.io/aridhia-open-source/fn_task_controller:1.2.0
TESTS_IMAGE ?= ghcr.io/aridhia-open-source/fn_task_controller_tests
TEST_CONTAINER ?= fn-controller-tests

build_container:
	docker build . -t "${IMAGE}"

build_test_container:
	docker build . -f test.Dockerfile -t ${TESTS_IMAGE}

build_helper:
	docker build build/helper -t ghcr.io/aridhia-open-source/fn_task_controller_helper:1.0.0

run_test_container: cleanup_test_container
	docker run --name ${TEST_CONTAINER} ${TESTS_IMAGE}
	docker cp ${TEST_CONTAINER}:/app/artifacts/coverage.xml artifacts/coverage.xml

cleanup_test_container:
	docker rm ${TEST_CONTAINER} || echo "No ${TEST_CONTAINER} container exists"

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
	pytest -v --cov-report xml:artifacts/coverage.xml --cov=controller controller

tests_ci: build_test_container run_test_container cleanup_test_container

pylint_ci:
	./scripts/linting/pylint.sh

hadolint:
	./scripts/tests/hadolint.sh

chart:
	helm package k8s/fn-task-controller -d artifacts/

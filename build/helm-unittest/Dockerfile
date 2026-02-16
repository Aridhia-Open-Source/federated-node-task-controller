FROM helmunittest/helm-unittest:3.19.0-1.0.3

COPY --chown=helmuser:helmgroup k8s/fn-task-controller/ /apps/chart
WORKDIR /apps/chart

CMD ["."]

FROM helmunittest/helm-unittest:3.18.4-1.0.0

COPY --chown=helmuser:helmgroup k8s/fn-task-controller/ /apps/chart
WORKDIR /apps/chart

CMD ["."]

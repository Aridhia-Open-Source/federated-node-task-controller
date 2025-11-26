{{/*
Expand the name of the chart.
*/}}
{{- define "fn-task-controller.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fn-task-controller.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "fn-task-controller.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fn-task-controller.labels" -}}
helm.sh/chart: {{ include "fn-task-controller.chart" . }}
{{ include "fn-task-controller.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fn-task-controller.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fn-task-controller.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fn-task-controller.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "fn-task-controller.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
{{- define "fn-task-controller.image" -}}
{{- print "ghcr.io/aridhia-open-source/fn_task_controller" -}}
{{- end }}
{{- define "fn-task-controller.helper-image" -}}
{{- print "ghcr.io/aridhia-open-source/fn_task_controller_helper" -}}
{{- end }}
{{- define "fn-task-controller.gitpath" -}}
{{- print "/data/git" -}}
{{- end }}
{{- define "controller_ns" -}}
{{- ((.Values.global).namespaces).controller | default .Values.namespaces.controller -}}
{{- end }}
{{- define "tasks_ns" -}}
{{- ((.Values.global).namespaces).tasks | default .Values.namespaces.tasks -}}
{{- end }}
{{- define "kc_ns" -}}
{{- ((.Values.global).namespaces).keycloak | default .Values.namespaces.keycloak -}}
{{- end }}
{{- define "rollMe" -}}
{{ randAlphaNum 5 | quote }}
{{- end -}}
{{- define "fn-alpine" -}}
ghcr.io/aridhia-open-source/alpine:{{ .Values.fnalpine.tag | default "3.19" }}
{{- end }}

{{- define "pvcControllerName" -}}
{{ printf "task-controller-%s-pv-volclaim" (.Values.storage.capacity | default "1Gi") | lower }}
{{- end }}
{{- define "pvControllerName" -}}
{{ printf "task-controller-%s-pv" (.Values.storage.capacity | default "1Gi") | lower }}
{{- end }}

{{- define "awsStorageAccount" -}}
{{- with .Values.storage.aws }}
  {{- if not .fileSystemId }}
    {{ fail "fileSystemId is necessary" }}
  {{- end }}
  {{- if .accessPointId }}
    {{- printf  "%s::%s" .fileSystemId .accessPointId | quote }}
  {{- else }}
    {{- .fileSystemId | quote }}
  {{- end }}
{{- end }}
{{- end -}}

{{- define "controllerStorageClass" -}}
{{ .Release.Name }}-controller-results
{{- end -}}
{{- define "controllerCrdGroup" -}}
tasks.federatednode.com
{{- end -}}
{{- define "areWeSubchart" -}}
{{- not (eq .Release.Name .Chart.Name) -}}
{{- end -}}

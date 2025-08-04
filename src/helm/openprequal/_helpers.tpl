# File: helm/openprequal/templates/_helpers.tpl
{{/* Generate chart name */}}
{{- define "openprequal.name" -}}
{{ .Chart.Name }}
{{- end }}

{{/* Generate full name */}}
{{- define "openprequal.fullname" -}}
{{ .Release.Name }}-{{ .Chart.Name }}
{{- end }}

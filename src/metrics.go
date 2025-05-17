// File: metrics.go
package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	probeRequestsTotal = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "prequal_probe_requests_total",
			Help: "Total number of probe requests received",
		},
	)

	proxyRequestsTotal = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "prequal_proxy_requests_total",
			Help: "Total number of proxy requests handled",
		},
	)

	rifGauge = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "prequal_rif",
			Help: "Current number of requests in flight",
		},
	)
)

func InitMetrics() {
	prometheus.MustRegister(probeRequestsTotal)
	prometheus.MustRegister(proxyRequestsTotal)
	prometheus.MustRegister(rifGauge)
}

func MetricsHandler() http.Handler {
	return promhttp.Handler()
}

func IncProbeRequests() {
	probeRequestsTotal.Inc()
}

func IncProxyRequests() {
	proxyRequestsTotal.Inc()
}

func SetCurrentRIF(rif int) {
	rifGauge.Set(float64(rif))
}
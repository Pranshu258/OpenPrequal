// File: proxy_handler.go
package main

import (
	"io"
	"log"
	"net/http"
	"net/url"
)

func ProxyHandler(selector *ReplicaSelector) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		replica, err := selector.SelectReplica()
		if err != nil {
			http.Error(w, "No healthy replicas available", http.StatusServiceUnavailable)
			return
		}

		targetURL := "http://" + replica + r.URL.Path
		proxyReq, err := http.NewRequest(r.Method, targetURL, r.Body)
		if err != nil {
			http.Error(w, "Failed to create proxy request", http.StatusInternalServerError)
			return
		}

		// Copy headers from original request
		proxyReq.Header = r.Header.Clone()

		resp, err := http.DefaultClient.Do(proxyReq)
		if err != nil {
			http.Error(w, "Proxy request failed", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		// Copy response headers and status code
		for k, v := range resp.Header {
			w.Header()[k] = v
		}
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

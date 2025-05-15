// File: rif_tracker.go
package main

import (
	"net/http"
	"sync/atomic"
)

var requestsInFlight int32 = 0

// RIFMiddleware wraps an HTTP handler and tracks the number of requests in flight
func RIFMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&requestsInFlight, 1)
		defer atomic.AddInt32(&requestsInFlight, -1)
		next.ServeHTTP(w, r)
	})
}

// GetCurrentRIF returns the current number of in-flight requests
func GetCurrentRIF() int {
	return int(atomic.LoadInt32(&requestsInFlight))
} 

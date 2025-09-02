package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081" // default port
	}
	host := os.Getenv("HOST")
	if host == "" {
		host = "localhost"
	}
	url := fmt.Sprintf("http://%s:%s", host, port)

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Backend-Url", url)
		msg := fmt.Sprintf("Hello from backend at %s\n", url)
		w.Write([]byte(msg))
	})

	log.Printf("Backend server listening at %s\n", url)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

package config

import (
	"os"
	"strconv"
)

// Config holds application configuration loaded from environment variables.
type Config struct {
	ProxyURL             string
	BackendPort          string
	BackendHost          string
	BackendURL           string
	HeartbeatSeconds     int
	HeartbeatTimeout     int
	LatencyWindowSec     int
	BackendHealthPath    string
	CustomRegisterHook   string
	CustomUnregisterHook string
	CustomPathRewrite    string
	CustomRequestHook    string
	CustomResponseHook   string
	LoadBalancerClass    string
}

// NewFromEnv creates a Config by reading environment variables and applying defaults.
func NewFromEnv() *Config {
	c := &Config{}
	c.ProxyURL = getenv("PROXY_URL", "http://localhost:8000")
	c.BackendPort = getenv("BACKEND_PORT", "8001")
	c.BackendHost = os.Getenv("BACKEND_HOST")

	// BACKEND_URL logic: prefer BACKEND_URL, else construct from host+port or localhost
	if v := os.Getenv("BACKEND_URL"); v != "" {
		c.BackendURL = v
	} else if c.BackendHost != "" {
		c.BackendURL = "http://" + c.BackendHost + ":" + c.BackendPort
	} else {
		c.BackendURL = "http://localhost:" + c.BackendPort
	}

	c.HeartbeatSeconds = getenvInt("BACKEND_HEARTBEAT_SECONDS", 30)
	c.HeartbeatTimeout = getenvInt("BACKEND_HEARTBEAT_TIMEOUT", 2*c.HeartbeatSeconds)
	c.LatencyWindowSec = getenvInt("LATENCY_WINDOW_SECONDS", 300)

	c.BackendHealthPath = getenv("BACKEND_HEALTH_PATH", "/probe")

	c.CustomRegisterHook = os.Getenv("CUSTOM_REGISTER_HOOK")
	c.CustomUnregisterHook = os.Getenv("CUSTOM_UNREGISTER_HOOK")
	c.CustomPathRewrite = os.Getenv("CUSTOM_PATH_REWRITE")
	c.CustomRequestHook = os.Getenv("CUSTOM_REQUEST_HOOK")
	c.CustomResponseHook = os.Getenv("CUSTOM_RESPONSE_HOOK")

	c.LoadBalancerClass = getenv("LOAD_BALANCER_CLASS", "default")

	return c
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func getenvInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return def
}

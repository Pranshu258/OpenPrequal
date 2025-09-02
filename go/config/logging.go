package config

import (
	"io"
	"log"
	"os"
	"path/filepath"
)

// LogLevel stores the effective log level (informational only, no enforcement).
var LogLevel = ""

const (
	defaultLogLevel = "INFO"
	defaultLogFile  = "logs/openprequal.log"
)

// SetupLogging configures the standard library logger to write to both stdout and a file.
// It creates the directory for the log file if necessary.
func SetupLogging() error {
	level := getenv("LOG_LEVEL", defaultLogLevel)
	file := getenv("LOG_FILE", defaultLogFile)

	// ensure directory exists
	dir := filepath.Dir(file)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}

	f, err := os.OpenFile(file, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}

	mw := io.MultiWriter(os.Stdout, f)
	log.SetOutput(mw)
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	LogLevel = level
	return nil
}

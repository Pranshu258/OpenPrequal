package core

import (
	"io"
	"net/http"
)

type ProxyHandler struct {
	client *http.Client
}

func NewProxyHandler(client *http.Client) *ProxyHandler { return &ProxyHandler{client: client} }

func (p *ProxyHandler) HandleProxy(req *http.Request, backendURL string) (*http.Response, error) {
	if backendURL == "" {
		return &http.Response{StatusCode: 503, Body: io.NopCloser(nil)}, nil
	}
	// in full implementation we'd rewrite path and forward headers/body
	outReq, _ := http.NewRequest(req.Method, backendURL+req.URL.Path, req.Body)
	outReq.Header = req.Header
	resp, err := p.client.Do(outReq)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

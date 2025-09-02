package algorithms

import (
	"openprequal/abstractions"
	"openprequal/contracts"
)

type RoundRobin struct {
	reg abstractions.Registry
	idx int
}

func NewRoundRobin(reg abstractions.Registry) *RoundRobin { return &RoundRobin{reg: reg} }

func (r *RoundRobin) Next() *contracts.Backend {
	list := r.reg.ListBackends()
	healthy := make([]contracts.Backend, 0)
	for _, b := range list {
		if b.Health {
			healthy = append(healthy, b)
		}
	}
	if len(healthy) == 0 {
		return nil
	}
	b := healthy[r.idx%len(healthy)]
	r.idx = (r.idx + 1) % len(healthy)
	return &b
}

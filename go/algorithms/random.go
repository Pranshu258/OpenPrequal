package algorithms

import (
	"math/rand"
	"openprequal/abstractions"
	"openprequal/contracts"
)

type RandomLB struct{ reg abstractions.Registry }

func NewRandomLB(r abstractions.Registry) *RandomLB { return &RandomLB{reg: r} }
func (r *RandomLB) Next() *contracts.Backend {
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
	i := rand.Intn(len(healthy))
	return &healthy[i]
}

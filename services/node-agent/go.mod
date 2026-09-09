module github.com/egparadise/SaintVision-Invion/services/node-agent

go 1.23

require (
	github.com/egparadise/SaintVision-Invion/packages/contracts-go v0.0.0
	github.com/santhosh-tekuri/jsonschema/v6 v6.0.2
)

require golang.org/x/text v0.14.0 // indirect

replace github.com/egparadise/SaintVision-Invion/packages/contracts-go => ../../packages/contracts-go

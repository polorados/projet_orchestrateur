# Orchestrator Project
Welcome to our SDWAN orchestrator project

To create the topology do :
```bash
mkdir ../sdwlab
cp lab_test.py ../sdwlab
cp config.py ../sdwlab
cd ../sdwlab
python lab_test.py
```

We thought of doing something like this 

```mermaid
stateDiagram-v2
probe1 --> Measurement_server
probe2 --> Measurement_server
probe3 --> Measurement_server
... --> Measurement_server
Measurement_server --> Orchestrator_server : json format 1
Orchestrator_server --> Configurer_server : json format 2
Configurer_server --> router1
Configurer_server --> router2
Configurer_server --> router3
Configurer_server --> ....
```


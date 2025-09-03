import uuid
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

class Node:
    def __init__(self, node_id, network):
        self.id = node_id
        self.network = network
        self.ledger = []
        self.pq_key_pair = self.generate_pq_keys()
        self.qubit_measurement_result = None
        # New attributes for leader election
        self.round_beacon = None
        self.round_leader = None

    def generate_pq_keys(self):
        private_key = uuid.uuid4().hex
        public_key = uuid.uuid4().hex
        return (private_key, public_key)
    
    def receive_quantum_measurement(self, outcome):
        self.qubit_measurement_result = int(outcome)
        # print(f"Node {self.id}: Received measurement outcome {self.qubit_measurement_result}.")

    # New method for calculating the leader
    def calculate_leader(self):
        """Calculates the round leader based on all measurement outcomes."""
        all_outcomes = self.network.get_all_measurements()
        
        # Calculate the random beacon 'R' via XOR sum
        beacon = 0
        for outcome in all_outcomes:
            beacon ^= outcome
        self.round_beacon = beacon
        
        # Determine the leader using the beacon
        num_nodes = self.network.num_nodes
        leader_id = self.round_beacon % num_nodes
        self.round_leader = leader_id
        
        print(f"Node {self.id}: Calculated beacon R={self.round_beacon}, determined Leader is Node {self.round_leader}.")

    def __repr__(self):
        return f"Node(id={self.id})"

class Network:
    def __init__(self, num_nodes):
        self.num_nodes = num_nodes
        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.simulator = AerSimulator()
        print(f"Network created with {self.num_nodes} nodes.")

    def get_node(self, node_id):
        return self.nodes[node_id]

    def broadcast_classical(self, sender_id, message):
        pass

    def create_ghz_circuit(self):
        circuit = QuantumCircuit(self.num_nodes, self.num_nodes)
        circuit.h(0)
        for i in range(self.num_nodes - 1):
            circuit.cx(i, i + 1)
        circuit.barrier()
        circuit.measure(range(self.num_nodes), range(self.num_nodes))
        return circuit

    def distribute_entangled_states_and_measure(self):
        print("\n--- QUANTUM CHANNEL: Round Start ---")
        ghz_circuit = self.create_ghz_circuit()
        compiled_circuit = transpile(ghz_circuit, self.simulator)
        result = self.simulator.run(compiled_circuit, shots=1, memory=True).result()
        measurement_outcomes = result.get_memory(compiled_circuit)[0]
        
        print(f"Simulated GHZ Measurement: {measurement_outcomes}")

        for i, node in enumerate(self.nodes):
            outcome_for_node = measurement_outcomes[::-1][i]
            node.receive_quantum_measurement(outcome_for_node)
        
        print("--- QUANTUM CHANNEL: Round End ---\n")

    # New method to simulate classical gathering of results
    def get_all_measurements(self):
        """Allows a node to gather all measurement results via classical channels."""
        return [node.qubit_measurement_result for node in self.nodes]


# --- Main Execution ---
if __name__ == "__main__":
    NUM_PARTIES = 4
    network = Network(NUM_PARTIES)
    
    # 1. Quantum Measurement Phase
    network.distribute_entangled_states_and_measure()

    # 2. Leader Election Phase
    print("--- LEADER ELECTION: Round Start ---")
    for node in network.nodes:
        node.calculate_leader()
    print("--- LEADER ELECTION: Round End ---\n")
    
    # Verification: Check if all nodes agreed on the same leader
    first_node_leader = network.get_node(0).round_leader
    all_leaders_match = all(
        network.get_node(i).round_leader == first_node_leader 
        for i in range(NUM_PARTIES)
    )
    the_leader = network.get_node(0).round_leader
    print(f"Verification: All nodes agreed on the same leader (Node {the_leader})? {all_leaders_match}")
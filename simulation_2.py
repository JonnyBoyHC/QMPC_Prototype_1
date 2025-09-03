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
        self.qubit_measurement_result = None # To store the outcome from the quantum channel

    def generate_pq_keys(self):
        # Placeholder for PQC keys.
        private_key = uuid.uuid4().hex
        public_key = uuid.uuid4().hex
        return (private_key, public_key)
    
    # New method for receiving the measurement outcome
    def receive_quantum_measurement(self, outcome):
        """Receives the classical result of the qubit measurement."""
        self.qubit_measurement_result = int(outcome)
        print(f"Node {self.id}: Received measurement outcome {self.qubit_measurement_result}.")

    def __repr__(self):
        return f"Node(id={self.id})"

class Network:
    def __init__(self, num_nodes):
        self.num_nodes = num_nodes
        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.simulator = AerSimulator() # Create a single simulator instance for efficiency
        print(f"Network created with {self.num_nodes} nodes.")

    def get_node(self, node_id):
        return self.nodes[node_id]

    def broadcast_classical(self, sender_id, message):
        print(f"CLASSICAL_BROADCAST from Node {sender_id}: {message}")
        for node in self.nodes:
            if node.id != sender_id:
                # In a real simulation, you'd add a method on the Node class
                # to handle incoming classical messages.
                pass

    def create_ghz_circuit(self):
        """Creates a GHZ state quantum circuit for all nodes."""
        # A quantum circuit with one qubit per node and one classical bit for each measurement
        circuit = QuantumCircuit(self.num_nodes, self.num_nodes)
        # Create entanglement: Start with a Hadamard gate on the first qubit
        circuit.h(0)
        # Cascade CNOT gates to entangle all other qubits
        for i in range(self.num_nodes - 1):
            circuit.cx(i, i + 1)
        # Add a barrier for visualization to separate entanglement from measurement
        circuit.barrier()
        # Measure all qubits
        circuit.measure(range(self.num_nodes), range(self.num_nodes))
        return circuit

    def distribute_entangled_states_and_measure(self):
        """Simulates creating a GHZ state, distributing it, and measuring."""
        print("\n--- QUANTUM CHANNEL: Round Start ---")
        ghz_circuit = self.create_ghz_circuit()
        print("Generated GHZ Circuit:")
        print(ghz_circuit)

        # Transpile the circuit for the simulator for better performance
        compiled_circuit = transpile(ghz_circuit, self.simulator)

        # Execute the circuit. We run it once (shots=1) for a single consensus round.
        result = self.simulator.run(compiled_circuit, shots=1, memory=True).result()
        # The 'memory' gives us the raw measurement outcomes, e.g., '1111' or '0000'
        measurement_outcomes = result.get_memory(compiled_circuit)[0]
        
        print(f"Simulated Measurement Result: {measurement_outcomes}")

        # Distribute the classical outcomes to each node
        for i, node in enumerate(self.nodes):
            # Qiskit's results are right-to-left, so we reverse for intuitive mapping
            outcome_for_node = measurement_outcomes[::-1][i]
            node.receive_quantum_measurement(outcome_for_node)
        
        print("--- QUANTUM CHANNEL: Round End ---\n")
        return measurement_outcomes

# --- Main Execution ---
if __name__ == "__main__":
    NUM_PARTIES = 4
    network = Network(NUM_PARTIES)
    
    # Execute one round of the quantum protocol
    outcomes = network.distribute_entangled_states_and_measure()

    # Verification: Check if all nodes received the same correlated bit
    first_node_result = network.get_node(0).qubit_measurement_result
    all_results_match = all(
        network.get_node(i).qubit_measurement_result == first_node_result 
        for i in range(NUM_PARTIES)
    )
    print(f"Verification: All nodes have the same measurement outcome? {all_results_match}")
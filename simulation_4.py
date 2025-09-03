import uuid
import time
import hashlib
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

# New Data Structure for a Transaction
class Transaction:
    def __init__(self, sender_id, receiver_id, amount):
        self.sender = sender_id
        self.receiver = receiver_id
        self.amount = amount
        self.timestamp = time.time()
        self.id = hashlib.sha256(str(self.__dict__).encode()).hexdigest()

    def __repr__(self):
        return f"Tx(id={self.id[:6]}..., from={self.sender}, to={self.receiver}, amt={self.amount})"

# New Data Structure for a Block
class Block:
    def __init__(self, proposer_id, round_num, transactions):
        self.proposer_id = proposer_id
        self.round = round_num
        self.transactions = transactions
        self.timestamp = time.time()
        self.hash = self.compute_hash()
        self.signature = None

    def compute_hash(self):
        # We exclude the signature from the hash calculation
        block_dict = self.__dict__.copy()
        block_dict.pop('signature', None)
        return hashlib.sha256(str(block_dict).encode()).hexdigest()

    def __repr__(self):
        return f"Block(round={self.round}, proposer={self.proposer_id}, hash={self.hash[:6]}..., txs={len(self.transactions)})"

class Node:
    def __init__(self, node_id, network):
        self.id = node_id
        self.network = network
        self.ledger = [] 
        self.pq_key_pair = self.generate_pq_keys()
        self.qubit_measurement_result = None
        self.round_beacon = None
        self.round_leader = None
        self.pending_block = None # To store a block proposal received for voting

    def generate_pq_keys(self):
        private_key, public_key = (uuid.uuid4().hex, uuid.uuid4().hex)
        return (private_key, public_key)
    
    def sign_block(self, block):
        # Placeholder for a PQC signature
        private_key = self.pq_key_pair[0]
        signature = hashlib.sha256(f"{block.hash}{private_key}".encode()).hexdigest()
        block.signature = signature
        return signature

    def receive_quantum_measurement(self, outcome):
        self.qubit_measurement_result = int(outcome)

    def calculate_leader(self):
        all_outcomes = self.network.get_all_measurements()
        beacon = 0
        for outcome in all_outcomes:
            beacon ^= outcome
        self.round_beacon = beacon
        leader_id = self.round_beacon % self.network.num_nodes
        self.round_leader = leader_id

    # New method to propose a block if this node is the leader
    def propose_block(self, round_num):
        if self.id == self.round_leader:
            print(f"Node {self.id}: I am the leader. Proposing a new block for round {round_num}.")
            # For simplicity, we create some dummy transactions
            txs = [Transaction(self.id, (self.id + 1) % self.network.num_nodes, 100)]
            new_block = Block(self.id, round_num, txs)
            self.sign_block(new_block)
            self.network.broadcast_classical("PROPOSE", new_block)
        
    # New method to handle incoming block proposals
    def receive_block_proposal(self, block):
        print(f"Node {self.id}: Received block proposal from Node {block.proposer_id}.")
        # Basic validation for now
        if block.proposer_id == self.round_leader:
            self.pending_block = block
        else:
            print(f"Node {self.id}: Discarding block from non-leader Node {block.proposer_id}.")

    def __repr__(self):
        return f"Node(id={self.id})"

class Network:
    def __init__(self, num_nodes):
        self.num_nodes = num_nodes
        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.simulator = AerSimulator()

    def get_node(self, node_id):
        return self.nodes[node_id]

    def broadcast_classical(self, message_type, data):
        """Simulates a classical broadcast to all nodes."""
        print(f"NETWORK_BROADCAST: Type={message_type}, Data={data}")
        for node in self.nodes:
            if message_type == "PROPOSE":
                # Don't send the proposal to the proposer itself
                if node.id != data.proposer_id:
                    node.receive_block_proposal(data)

    def create_ghz_circuit(self):
        circuit = QuantumCircuit(self.num_nodes, self.num_nodes)
        circuit.h(0)
        for i in range(self.num_nodes - 1):
            circuit.cx(i, i + 1)
        circuit.barrier()
        circuit.measure(range(self.num_nodes), range(self.num_nodes))
        return circuit

    def distribute_entangled_states_and_measure(self):
        ghz_circuit = self.create_ghz_circuit()
        compiled_circuit = transpile(ghz_circuit, self.simulator)
        result = self.simulator.run(compiled_circuit, shots=1, memory=True).result()
        measurement_outcomes = result.get_memory(compiled_circuit)[0]
        
        for i, node in enumerate(self.nodes):
            outcome_for_node = measurement_outcomes[::-1][i]
            node.receive_quantum_measurement(outcome_for_node)

    def get_all_measurements(self):
        return [node.qubit_measurement_result for node in self.nodes]

# --- Main Execution ---
if __name__ == "__main__":
    NUM_PARTIES = 4
    network = Network(NUM_PARTIES)
    current_round = 1
    
    # 1. Quantum Measurement Phase
    network.distribute_entangled_states_and_measure()

    # 2. Leader Election Phase
    for node in network.nodes:
        node.calculate_leader()
    
    the_leader_id = network.get_node(0).round_leader
    the_leader_node = network.get_node(the_leader_id)
    print(f"\n--- Leader for Round {current_round} is Node {the_leader_id} ---\n")

    # 3. Block Proposal Phase
    the_leader_node.propose_block(current_round)

    # Verification: Check if all other nodes have received the pending block
    print("\n--- Verification ---")
    all_nodes_received = all(
        network.get_node(i).pending_block is not None
        for i in range(NUM_PARTIES) if i != the_leader_id
    )
    print(f"All non-leader nodes received the block proposal? {all_nodes_received}")
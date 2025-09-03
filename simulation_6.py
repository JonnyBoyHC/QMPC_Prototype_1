import uuid
import time
import hashlib
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

# --- Data Structures ---
class Transaction:
    def __init__(self, sender_id, receiver_id, amount):
        self.sender = sender_id
        self.receiver = receiver_id
        self.amount = amount
        self.timestamp = time.time()
        self.id = hashlib.sha256(str(self.__dict__).encode()).hexdigest()

    def __repr__(self):
        return f"Tx(id={self.id[:6]}...)"

class Block:
    # Modified to include previous_hash for chaining
    def __init__(self, proposer_id, round_num, transactions, previous_hash):
        self.proposer_id = proposer_id
        self.round = round_num
        self.transactions = transactions
        self.previous_hash = previous_hash # Link to the previous block
        self.timestamp = time.time()
        self.hash = self.compute_hash()
        self.signature = None

    def compute_hash(self):
        block_dict = self.__dict__.copy()
        block_dict.pop('signature', None)
        # Use sorted items to ensure consistent hash
        return hashlib.sha256(str(sorted(block_dict.items())).encode()).hexdigest()

    def __repr__(self):
        return f"Block(round={self.round}, hash={self.hash[:6]}..., prev_hash={self.previous_hash[:6]}...)"

# --- Core Components ---
class Node:
    def __init__(self, node_id, network):
        self.id = node_id
        self.network = network
        self.ledger = [self.create_genesis_block()] # Start with the genesis block
        self.pq_key_pair = self.generate_pq_keys()
        self.reset_round_state()

    def reset_round_state(self):
        """Resets variables used in a single consensus round."""
        self.qubit_measurement_result = None
        self.round_leader = None
        self.pending_block = None
        self.commit_votes = {}
    
    def create_genesis_block(self):
        """Creates the very first block in the chain."""
        return Block(proposer_id=-1, round_num=0, transactions=[], previous_hash="0"*64)

    def generate_pq_keys(self):
        private_key, public_key = (uuid.uuid4().hex, uuid.uuid4().hex)
        return (private_key, public_key)
    
    def sign_message(self, message):
        private_key = self.pq_key_pair[0]
        return hashlib.sha256(f"{message}{private_key}".encode()).hexdigest()

    def receive_quantum_measurement(self, outcome):
        self.qubit_measurement_result = int(outcome)

    def calculate_leader(self):
        all_outcomes = self.network.get_all_measurements()
        beacon = 0
        for outcome in all_outcomes:
            beacon ^= outcome
        self.round_leader = beacon % self.network.num_nodes

    def propose_block(self, round_num):
        if self.id == self.round_leader:
            txs = [Transaction(self.id, (self.id + 1) % self.network.num_nodes, 10 * round_num)]
            previous_hash = self.ledger[-1].hash
            new_block = Block(self.id, round_num, txs, previous_hash)
            new_block.signature = self.sign_message(new_block.hash)
            self.network.broadcast_classical("PROPOSE", new_block)
        
    def receive_block_proposal(self, block):
        if block.proposer_id == self.round_leader and block.previous_hash == self.ledger[-1].hash:
            self.pending_block = block
            self.validate_and_vote()
        
    def validate_and_vote(self):
        if self.pending_block:
            vote_signature = self.sign_message(self.pending_block.hash)
            commit_vote = {"block_hash": self.pending_block.hash, "voter_id": self.id, "signature": vote_signature}
            self.network.broadcast_classical("COMMIT", commit_vote)

    def receive_commit_vote(self, vote):
        block_hash = vote["block_hash"]
        if self.pending_block and self.pending_block.hash == block_hash:
            if block_hash not in self.commit_votes:
                self.commit_votes[block_hash] = set()
            self.commit_votes[block_hash].add(vote["voter_id"])
            if len(self.commit_votes[block_hash]) == self.network.num_nodes:
                self.finalize_block(block_hash)

    def finalize_block(self, block_hash):
        print(f"Node {self.id}: 🎉 Finalizing block for round {self.pending_block.round}...")
        self.ledger.append(self.pending_block)
        self.reset_round_state()

    def __repr__(self):
        return f"Node(id={self.id}, ledger_height={len(self.ledger)})"

class Network:
    def __init__(self, num_nodes):
        self.num_nodes = num_nodes
        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.simulator = AerSimulator()

    def get_node(self, node_id):
        return self.nodes[node_id]

    def broadcast_classical(self, message_type, data):
        for node in self.nodes:
            if message_type == "PROPOSE":
                node.receive_block_proposal(data)
            elif message_type == "COMMIT":
                node.receive_commit_vote(data)

    def distribute_entangled_states_and_measure(self):
        circuit = QuantumCircuit(self.num_nodes, self.num_nodes)
        circuit.h(0)
        for i in range(self.num_nodes - 1):
            circuit.cx(i, i + 1)
        circuit.measure(range(self.num_nodes), range(self.num_nodes))
        compiled_circuit = transpile(circuit, self.simulator)
        result = self.simulator.run(compiled_circuit, shots=1, memory=True).result()
        measurement_outcomes = result.get_memory(compiled_circuit)[0]
        
        for i, node in enumerate(self.nodes):
            node.receive_quantum_measurement(measurement_outcomes[::-1][i])

    def get_all_measurements(self):
        return [node.qubit_measurement_result for node in self.nodes]

# New Simulation Manager
class Simulation:
    def __init__(self, num_nodes, num_rounds):
        self.network = Network(num_nodes)
        self.num_rounds = num_rounds

    def run_round(self, round_num):
        print(f"\n--- STARTING CONSENSUS ROUND {round_num} ---")
        # 1. Quantum Measurement & Leader Election
        self.network.distribute_entangled_states_and_measure()
        for node in self.network.nodes:
            node.calculate_leader()
        
        leader_id = self.network.get_node(0).round_leader
        print(f"Leader for Round {round_num} is Node {leader_id}.")

        # 2. Block Proposal (triggers validation and voting)
        leader_node = self.network.get_node(leader_id)
        leader_node.propose_block(round_num)

    def run(self):
        for i in range(1, self.num_rounds + 1):
            self.run_round(i)
        self.final_verification()
    
    def final_verification(self):
        print("\n--- FINAL VERIFICATION ---")
        first_node_ledger = self.network.get_node(0).ledger
        print(f"Node 0 final ledger height: {len(first_node_ledger)}")
        
        all_ledgers_match = True
        for i in range(1, self.network.num_nodes):
            other_node_ledger = self.network.get_node(i).ledger
            if len(first_node_ledger) != len(other_node_ledger):
                all_ledgers_match = False
                break
            if any(b1.hash != b2.hash for b1, b2 in zip(first_node_ledger, other_node_ledger)):
                all_ledgers_match = False
                break
        
        print(f"All node ledgers are identical? {all_ledgers_match}")


# --- Main Execution ---
if __name__ == "__main__":
    sim = Simulation(num_nodes=4, num_rounds=3)
    sim.run()
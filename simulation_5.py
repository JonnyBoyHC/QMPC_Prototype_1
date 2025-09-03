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
    def __init__(self, proposer_id, round_num, transactions):
        self.proposer_id = proposer_id
        self.round = round_num
        self.transactions = transactions
        self.timestamp = time.time()
        self.hash = self.compute_hash()
        self.signature = None

    def compute_hash(self):
        block_dict = self.__dict__.copy()
        block_dict.pop('signature', None)
        return hashlib.sha256(str(sorted(block_dict.items())).encode()).hexdigest()

    def __repr__(self):
        return f"Block(round={self.round}, hash={self.hash[:6]}...)"

# --- Core Components ---
class Node:
    def __init__(self, node_id, network):
        self.id = node_id
        self.network = network
        self.ledger = [] 
        self.pq_key_pair = self.generate_pq_keys()
        # State for the current round
        self.qubit_measurement_result = None
        self.round_leader = None
        self.pending_block = None
        self.commit_votes = {} # Tracks votes for blocks: {block_hash: {voter_ids}}

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
            txs = [Transaction(self.id, (self.id + 1) % self.network.num_nodes, 100)]
            new_block = Block(self.id, round_num, txs)
            new_block.signature = self.sign_message(new_block.hash)
            self.network.broadcast_classical("PROPOSE", new_block)
        
    def receive_block_proposal(self, block):
        # Basic validation: is the proposer the correct leader?
        if block.proposer_id == self.round_leader:
            self.pending_block = block
            print(f"Node {self.id}: Received and accepted pending block {block.hash[:6]}...")
            self.validate_and_vote() # Immediately validate and vote
        else:
            print(f"Node {self.id}: Discarded block from non-leader {block.proposer_id}.")

    # New method for validation and voting
    def validate_and_vote(self):
        if self.pending_block:
            # In a real system, we'd verify the block's signature and transactions.
            # Here, we just assume it's valid.
            vote_signature = self.sign_message(self.pending_block.hash)
            commit_vote = {"block_hash": self.pending_block.hash, "voter_id": self.id, "signature": vote_signature}
            self.network.broadcast_classical("COMMIT", commit_vote)

    # New method to receive and tally votes
    def receive_commit_vote(self, vote):
        block_hash = vote["block_hash"]
        voter_id = vote["voter_id"]
        
        # Initialize vote set for this block hash if it's the first vote
        if block_hash not in self.commit_votes:
            self.commit_votes[block_hash] = set()
        
        self.commit_votes[block_hash].add(voter_id)
        print(f"Node {self.id}: Received COMMIT for block {block_hash[:6]} from Node {voter_id}. Total votes: {len(self.commit_votes[block_hash])}")

        # Check for consensus threshold. For simplicity, we require all nodes to vote.
        # In BFT, this would be 2f+1.
        if len(self.commit_votes[block_hash]) == self.network.num_nodes:
            self.finalize_block(block_hash)

    # New method to finalize the block
    def finalize_block(self, block_hash):
        if self.pending_block and self.pending_block.hash == block_hash:
            print(f"Node {self.id}: 🎉 Consensus reached! Finalizing block {block_hash[:6]}...")
            self.ledger.append(self.pending_block)
            # Reset state for the next round
            self.pending_block = None
            self.commit_votes = {}

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
        if message_type == "PROPOSE":
            # Proposer also "receives" its own proposal to trigger voting
            for node in self.nodes:
                node.receive_block_proposal(data)
        elif message_type == "COMMIT":
            for node in self.nodes:
                node.receive_commit_vote(data)

    def distribute_entangled_states_and_measure(self):
        ghz_circuit = QuantumCircuit(self.num_nodes, self.num_nodes)
        ghz_circuit.h(0)
        for i in range(self.num_nodes - 1):
            ghz_circuit.cx(i, i + 1)
        ghz_circuit.measure(range(self.num_nodes), range(self.num_nodes))
        compiled_circuit = transpile(ghz_circuit, self.simulator)
        result = self.simulator.run(compiled_circuit, shots=1, memory=True).result()
        measurement_outcomes = result.get_memory(compiled_circuit)[0]
        
        for i, node in enumerate(self.nodes):
            node.receive_quantum_measurement(measurement_outcomes[::-1][i])

    def get_all_measurements(self):
        return [node.qubit_measurement_result for node in self.nodes]

# --- Main Execution ---
if __name__ == "__main__":
    NUM_PARTIES = 4
    network = Network(NUM_PARTIES)
    current_round = 1
    
    print(f"--- STARTING CONSENSUS ROUND {current_round} ---\n")
    # 1. Quantum Measurement & Leader Election
    network.distribute_entangled_states_and_measure()
    for node in network.nodes:
        node.calculate_leader()
    
    the_leader_id = network.get_node(0).round_leader
    print(f"Leader for Round {current_round} is Node {the_leader_id}.\n")

    # 2. Block Proposal (triggers validation and voting)
    leader_node = network.get_node(the_leader_id)
    leader_node.propose_block(current_round)

    # 3. Final Verification
    print("\n--- FINAL VERIFICATION ---")
    first_node_ledger = network.get_node(0).ledger
    if not first_node_ledger:
        print("Error: No block was finalized.")
    else:
        final_block_hash = first_node_ledger[-1].hash
        all_nodes_finalized = all(
            len(node.ledger) == 1 and node.ledger[-1].hash == final_block_hash
            for node in network.nodes
        )
        print(f"All nodes finalized the same block ({final_block_hash[:6]})? {all_nodes_finalized}")
        print("\nFinal State of Nodes:")
        for node in network.nodes:
            print(node)
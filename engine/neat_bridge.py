import numpy as np

class NeatBridge:
    """
    Translates NEAT genomes into vectorized NumPy tensors for the ComputeEngine.
    Supports up to max_capacity (100) for mid-generation cloning.
    """
    def __init__(self, num_inputs=13, num_outputs=4, max_nodes=50):
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs
        self.max_nodes = max_nodes

    def compile_population(self, genomes, config, max_capacity=100):
        """
        Returns: W (100, N, N), b (100, N), conn_counts (100)
        First N slots are filled with the initial pop_size (50). The rest are zeros.
        """
        W = np.zeros((max_capacity, self.max_nodes, self.max_nodes), dtype=np.float32)
        b = np.zeros((max_capacity, self.max_nodes), dtype=np.float32)
        conn_counts = np.zeros(max_capacity, dtype=np.int32)
        
        input_keys = config.genome_config.input_keys
        output_keys = config.genome_config.output_keys
        
        for i, (genome_id, genome) in enumerate(genomes):
            if i >= max_capacity:
                break
                
            node_mapping = {}
            for j, node_id in enumerate(input_keys):
                node_mapping[node_id] = j
            for j, node_id in enumerate(output_keys):
                node_mapping[node_id] = self.num_inputs + j
                
            hidden_idx = self.num_inputs + self.num_outputs
            for node_id in genome.nodes:
                if node_id not in node_mapping:
                    if hidden_idx >= self.max_nodes:
                        break
                    node_mapping[node_id] = hidden_idx
                    hidden_idx += 1
                    
            for node_id, node in genome.nodes.items():
                if node_id in node_mapping:
                    b[i, node_mapping[node_id]] = node.bias
                    
            count = 0
            for cg_key, cg in genome.connections.items():
                if cg.enabled:
                    in_node, out_node = cg_key
                    if in_node in node_mapping and out_node in node_mapping:
                        W[i, node_mapping[in_node], node_mapping[out_node]] = cg.weight
                        count += 1
            conn_counts[i] = count
                        
        return W, b, conn_counts


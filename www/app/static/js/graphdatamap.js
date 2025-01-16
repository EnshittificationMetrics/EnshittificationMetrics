document.addEventListener('DOMContentLoaded', function () {
	console.log('DOM fully loaded and parsed');
	console.log('dataMap:', dataMap);
	// Initialize Cytoscape
	const cy = cytoscape({
		container: document.getElementById('cy_datamap'),
		elements: {
			nodes: dataMap.nodes, // passed from html by const dataMap
			edges: dataMap.edges,
		},
		style: [
			{
				selector: 'node',
				style: {
					'background-color': '#0074D9',
					'label': 'data(label)',
					'color': '#fff',
					'text-valign': 'center',
					'text-halign': 'center',
				}
			},
			{
				selector: 'edge',
				style: {
					'width': 3,
					'line-color': '#FF4136',
					'target-arrow-color': '#FF4136',
					'target-arrow-shape': 'triangle',
					'curve-style': 'bezier',
				}
			}
		],
		layout: {
			name: 'breadthfirst', // Layout style - circle or grid or breadthfirst
		},
	});

	// Add interactivity: alert when a node is clicked
	cy.on('tap', 'node', function(evt) {
		const node = evt.target;
		alert(`Clicked on node ${node.id()}`); // also node.data() node.position() node.connectedEdges() node.degree() node.style() node.classes() node.parent()
	});
})
.catch(error => console.error('Error loading graph data:', error));

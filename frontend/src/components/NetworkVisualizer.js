import React, { useEffect, useRef } from "react";
import * as d3 from "d3";
import "./NetworkVisualizer.css";

const getIpToFilenameMap = (nodes, nodesData) => {
  const ipToFilenameMap = {};
  const filenames = Object.keys(nodes).sort();

  filenames.forEach((filename) => {
    const { node_ip, ip_address } = nodes[filename] || {};
    const ip = node_ip || ip_address;
    if (ip && nodesData.find((n) => n.id === ip)) {
      ipToFilenameMap[ip] = filename;
    }
  });

  if (Object.keys(ipToFilenameMap).length < nodesData.length) {
    filenames.forEach((filename, idx) => {
      if (idx < nodesData.length) {
        const ip = nodesData[idx].id;
        if (!ipToFilenameMap[ip]) {
          ipToFilenameMap[ip] = filename;
        }
      }
    });
  }

  return ipToFilenameMap;
};

const NetworkVisualizer = ({ nodes = {}, onSelectNode, selectedNode }) => {
  const svgRef = useRef(null);

  useEffect(() => {
    const SVG_W = 1000;
    const SVG_H = 560;
    const NODE_RADIUS = 26;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    svg
      .attr("viewBox", `0 0 ${SVG_W} ${SVG_H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");

    // Defs for gradients & filters
    const defs = svg.append("defs");
    
    // Glow filter
    const filter = defs.append("filter")
      .attr("id", "cyan-glow")
      .attr("x", "-20%")
      .attr("y", "-20%")
      .attr("width", "140%")
      .attr("height", "140%");
    filter.append("feGaussianBlur")
      .attr("stdDeviation", "4")
      .attr("result", "blur");
    filter.append("feComposite")
      .attr("in", "SourceGraphic")
      .attr("in2", "blur")
      .attr("operator", "over");

    // Background Grid Pattern
    const pattern = defs.append("pattern")
      .attr("id", "soc-grid")
      .attr("width", "40")
      .attr("height", "40")
      .attr("patternUnits", "userSpaceOnUse");
    pattern.append("path")
      .attr("d", "M 40 0 L 0 0 0 40")
      .attr("fill", "none")
      .attr("stroke", "#1e293b")
      .attr("stroke-width", "0.8")
      .attr("opacity", "0.4");

    svg.append("rect")
      .attr("width", SVG_W)
      .attr("height", SVG_H)
      .attr("fill", "url(#soc-grid)");

    // Tooltip
    d3.selectAll(".soc-node-tooltip").remove();
    const tooltip = d3
      .select("body")
      .append("div")
      .attr("class", "soc-node-tooltip tooltip")
      .style("opacity", 0);

    Promise.all([d3.json("/nodes_data.json"), d3.json("/packets_data.json")])
      .then(([nodesData, packetsData]) => {
        if (!nodesData?.length) return;

        const ipMap = getIpToFilenameMap(nodes, nodesData);

        // Normalize positions
        const enriched = nodesData.map((d) => {
          const key = ipMap[d.id] || d.id;
          const isAttack = !!nodes[key]?.attack_detected;
          return {
            ...d,
            attack_detected: isAttack,
            x: Math.max(NODE_RADIUS + 20, Math.min(d.x * 1.1 + 40, SVG_W - NODE_RADIUS - 20)),
            y: Math.max(NODE_RADIUS + 30, Math.min(d.y * 0.9 + 50, SVG_H - NODE_RADIUS - 30)),
          };
        });

        const nodePos = new Map(enriched.map((d) => [d.id, { x: d.x, y: d.y }]));

        // Draw Links Between Nodes
        const links = [];
        const seenLinks = new Set();
        (packetsData || []).forEach((pkt) => {
          const linkKey = [pkt.src, pkt.dst].sort().join("<->");
          if (!seenLinks.has(linkKey) && nodePos.has(pkt.src) && nodePos.has(pkt.dst)) {
            seenLinks.add(linkKey);
            links.push({
              source: nodePos.get(pkt.src),
              target: nodePos.get(pkt.dst),
            });
          }
        });

        // SVG Link Lines
        svg.append("g")
          .attr("class", "network-links")
          .selectAll("line")
          .data(links)
          .enter()
          .append("line")
          .attr("x1", (d) => d.source.x)
          .attr("y1", (d) => d.source.y)
          .attr("x2", (d) => d.target.x)
          .attr("y2", (d) => d.target.y)
          .attr("stroke", "#1e3a5f")
          .attr("stroke-width", "1.5")
          .attr("stroke-dasharray", "4,3")
          .attr("opacity", 0.6);

        // Draw Nodes
        const nodeGroups = svg
          .append("g")
          .attr("class", "network-nodes")
          .selectAll(".node")
          .data(enriched, (d) => d.id)
          .enter()
          .append("g")
          .attr("class", "node")
          .attr("transform", (d) => `translate(${d.x},${d.y})`);

        // Node Outer Ring (Selected State)
        nodeGroups
          .append("circle")
          .attr("class", "node-ring")
          .attr("r", NODE_RADIUS + 5)
          .attr("fill", "none")
          .attr("stroke", (d) => (d.id === selectedNode ? "#38bdf8" : "transparent"))
          .attr("stroke-width", 2)
          .attr("stroke-dasharray", "3 2");

        // Main Node Circle
        nodeGroups
          .append("circle")
          .attr("r", NODE_RADIUS)
          .attr("fill", (d) => (d.attack_detected ? "#ef4444" : "#10b981"))
          .attr("stroke", (d) => (d.attack_detected ? "#7f1d1d" : "#064e3b"))
          .attr("stroke-width", 2.5)
          .style("cursor", "pointer")
          .on("mouseover", function (evt, d) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr("r", NODE_RADIUS * 1.15)
              .attr("stroke", "#38bdf8");

            tooltip
              .html(`<strong>Node:</strong> ${d.id}<br/><strong>Status:</strong> ${d.attack_detected ? "Threat Detected" : "Nominal"}`)
              .style("left", `${evt.pageX + 10}px`)
              .style("top", `${evt.pageY - 30}px`)
              .transition()
              .duration(200)
              .style("opacity", 0.95);
          })
          .on("mouseout", function (evt, d) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr("r", NODE_RADIUS)
              .attr("stroke", d.attack_detected ? "#7f1d1d" : "#064e3b");

            tooltip.transition().duration(300).style("opacity", 0);
          })
          .on("click", (evt, d) => {
            if (onSelectNode) onSelectNode(d.id);
          });

        // Node IP Label
        nodeGroups
          .append("text")
          .attr("dy", -(NODE_RADIUS + 8))
          .attr("text-anchor", "middle")
          .style("font-size", "11px")
          .style("font-family", "JetBrains Mono, monospace")
          .style("fill", "#94a3b8")
          .style("pointer-events", "none")
          .text((d) => d.id);

        // Professional inner node core indicator (No emoji)
        nodeGroups
          .append("circle")
          .attr("r", 5)
          .attr("fill", (d) => (d.attack_detected ? "#fca5a5" : "#a7f3d0"))
          .style("pointer-events", "none");

        // Packet Flow Animation
        if (!packetsData || packetsData.length === 0) return;

        const t0 = d3.min(packetsData, (pkt) => pkt.timestamp_start);
        const msPerSecond = 8000;
        const playbackSpeed = 1;

        packetsData.forEach((pkt, i) => {
          const src = nodePos.get(pkt.src);
          const dst = nodePos.get(pkt.dst);
          if (!src || !dst) return;

          const delayMs = ((pkt.timestamp_start - t0) * msPerSecond) / playbackSpeed;
          const durMs = Math.max(1200, Math.min(2200, delayMs % 3000));

          svg
            .append("circle")
            .attr("class", "packet")
            .attr("r", 4)
            .attr("cx", src.x)
            .attr("cy", src.y)
            .attr("fill", "#38bdf8")
            .style("opacity", 0)
            .transition()
            .delay(delayMs % 4000)
            .style("opacity", 0.9)
            .duration(durMs)
            .attr("cx", dst.x)
            .attr("cy", dst.y)
            .transition()
            .duration(150)
            .style("opacity", 0)
            .remove();
        });
      })
      .catch((err) => console.error("Error loading topology:", err));

    return () => {
      tooltip.remove();
    };
  }, [nodes, onSelectNode, selectedNode]);

  return (
    <div className="network-visualization">
      <svg ref={svgRef} />
    </div>
  );
};

export default NetworkVisualizer;

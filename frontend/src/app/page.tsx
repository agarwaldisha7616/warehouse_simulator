"use client";

import React, { useState, useEffect, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Box, Cylinder, Text, Stars } from "@react-three/drei";
import * as THREE from "three";
import { RefreshCw, Play, SkipForward, LayoutGrid, AlertCircle, Package, Truck } from "lucide-react";

// Types
type RobotPosition = [number, number];
type PackageInfo = {
  id: string;
  position: [number, number];
  deadline: number;
  delivered: boolean;
};
type Task = {
  action: "move_to" | "move" | "pick" | "deliver" | "no_op";
  target?: string;
  direction?: "up" | "down" | "left" | "right";
  steps?: number;
};
type LLMPlan = {
  tasks: Task[];
  reasoning: string;
};
type ObservationWrapper = {
  done: boolean;
  reward: number | null;
  observation: {
    robot_position: RobotPosition;
    grid_size: number;
    packages: PackageInfo[];
    obstacles: [number, number][];
    steps_remaining: number;
    carrying_package: string | null;
    message: string;
    delivered_count: number;
    total_packages: number;
  };
};

const API_BASE = "http://localhost:7860";

// --- 3D Components ---

const Robot = ({ position, carrying, gridSize }: { position: RobotPosition, carrying: string | null, gridSize: number }) => {
  const meshRef = useRef<THREE.Group>(null);
  const safeGridSize = gridSize || 5;
  const offset = safeGridSize / 2 - 0.5;
  
  // Mapping: Grid X -> 3D X, Grid Y -> 3D Z
  const targetX = position ? position[0] - offset : 0; 
  const targetZ = position ? position[1] - offset : 0;
  
  const [prevPos, setPrevPos] = useState<RobotPosition>(position);
  const [rotation, setRotation] = useState(0);

  useFrame((state, delta) => {
    if (meshRef.current) {
      // Smooth interpolation
      meshRef.current.position.x = THREE.MathUtils.lerp(meshRef.current.position.x, targetX, 0.1);
      meshRef.current.position.z = THREE.MathUtils.lerp(meshRef.current.position.z, targetZ, 0.1);
      
      // Face movement direction
      if (position[0] !== prevPos[0] || position[1] !== prevPos[1]) {
        const dx = position[0] - prevPos[0];
        const dz = position[1] - prevPos[1];
        setRotation(Math.atan2(dx, dz));
        setPrevPos(position);
      }
      meshRef.current.rotation.y = THREE.MathUtils.lerp(meshRef.current.rotation.y, rotation, 0.1);
    }
  });

  return (
    <group ref={meshRef}>
      {/* Robot Body */}
      <Box args={[0.7, 0.5, 0.7]} position={[0, 0.25, 0]} castShadow>
        <meshStandardMaterial color={carrying ? "#f59e0b" : "#3b82f6"} metalness={0.5} roughness={0.2} />
      </Box>
      {/* Robot Eye/Front */}
      <Box args={[0.4, 0.2, 0.1]} position={[0, 0.35, 0.35]}>
        <meshStandardMaterial color="#1e293b" emissive="#60a5fa" emissiveIntensity={1} />
      </Box>
      {/* Carrying Indicator */}
      {carrying && (
        <Box args={[0.5, 0.5, 0.5]} position={[0, 0.75, 0]} castShadow>
          <meshStandardMaterial color="#ef4444" />
        </Box>
      )}
    </group>
  );
};

const PackageComponent = ({ pkg, gridSize, isTarget }: { pkg: PackageInfo, gridSize: number, isTarget?: boolean }) => {
  if (pkg.delivered) return null;
  const safeGridSize = gridSize || 5;
  const offset = safeGridSize / 2 - 0.5;
  
  return (
    <group position={[pkg.position[0] - offset, 0.25, pkg.position[1] - offset]}>
      <Box args={[0.5, 0.5, 0.5]} castShadow>
        <meshStandardMaterial 
          color={isTarget ? "#fbbf24" : "#ef4444"} 
          metalness={0.2} 
          roughness={0.5} 
          emissive={isTarget ? "#fbbf24" : "#000000"} 
          emissiveIntensity={isTarget ? 0.8 : 0} 
        />
      </Box>
      <Text
        position={[0, 0.7, 0]}
        fontSize={0.2}
        color="white"
        anchorX="center"
        anchorY="middle"
      >
        {pkg.id}
      </Text>
    </group>
  );
};

const Obstacle = ({ pos, gridSize }: { pos: [number, number], gridSize: number }) => {
  const safeGridSize = gridSize || 5;
  const offset = safeGridSize / 2 - 0.5;
  return (
    <Box args={[0.9, 1.5, 0.9]} position={[pos[0] - offset, 0.75, pos[1] - offset]} castShadow receiveShadow>
      <meshStandardMaterial color="#475569" metalness={0.1} roughness={0.9} />
    </Box>
  );
};

const Floor = ({ gridSize }: { gridSize: number }) => {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
      <planeGeometry args={[gridSize + 2, gridSize + 2]} />
      <meshStandardMaterial color="#0f172a" />
    </mesh>
  );
};

const DeliveryZone = ({ gridSize, isTarget }: { gridSize: number, isTarget?: boolean }) => {
  const safeGridSize = gridSize || 5;
  const offset = safeGridSize / 2 - 0.5;
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0 - offset, 0.01, 0 - offset]} receiveShadow>
      <planeGeometry args={[1, 1]} />
      <meshStandardMaterial 
        color={isTarget ? "#34d399" : "#10b981"} 
        opacity={isTarget ? 0.6 : 0.3} 
        transparent 
        emissive={isTarget ? "#34d399" : "#000000"} 
        emissiveIntensity={isTarget ? 0.5 : 0}
      />
    </mesh>
  );
};

// --- Main UI ---

export default function WarehouseSimulator() {
  const [obs, setObs] = useState<ObservationWrapper | null>(null);
  const [taskLevel, setTaskLevel] = useState("easy");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [mounted, setMounted] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);
  const [aiReasoning, setAiReasoning] = useState<string | null>(null);
  const [aiTarget, setAiTarget] = useState<string | null>(null);
  const [autoSpeed, setAutoSpeed] = useState<number>(500);
  const [showDebug, setShowDebug] = useState<boolean>(true);
  const [executionQueue, setExecutionQueue] = useState<Task[]>([]);
  const [currentTask, setCurrentTask] = useState<Task | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (executionQueue.length > 0) {
      const task = executionQueue[0];
      if (task.target) setAiTarget(task.target);
    }
  }, [executionQueue]);

  // Automatic execution loop
  useEffect(() => {
    let timeout: NodeJS.Timeout;
    if (isAutoPlaying && obs && !obs.done && !loading) {
      timeout = setTimeout(() => {
        runAutoStep();
      }, autoSpeed); // Dynamic delay based on speed setting
    } else if (obs?.done) {
      setIsAutoPlaying(false);
    }
    return () => clearTimeout(timeout);
  }, [isAutoPlaying, obs, loading, autoSpeed]);

  // Execution Queue Processor
  useEffect(() => {
    let timeout: NodeJS.Timeout;
    if (executionQueue.length > 0 && !loading && !obs?.done && !isAutoPlaying) {
      timeout = setTimeout(() => {
        processNextTask();
      }, autoSpeed);
    } else if (executionQueue.length === 0) {
      setCurrentTask(null);
    }
    return () => clearTimeout(timeout);
  }, [executionQueue, loading, obs, isAutoPlaying, autoSpeed]);

  const processNextTask = async () => {
    if (executionQueue.length === 0 || loading || obs?.done) return;

    const task = executionQueue[0];
    setCurrentTask(task);
    setLoading(true);

    try {
      // 1. Get next low-level action for this task
      const actionRes = await fetch(`${API_BASE}/task_to_action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(task),
      });
      const robot_action = await actionRes.json();

      // 2. Execute step
      const res = await fetch(`${API_BASE}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: robot_action }),
      });
      const data = await res.json();

      if (data && data.observation) {
        setObs(data);
        addLog(`[PLAN] ${task.action} (${task.target || task.direction}) -> ${robot_action.act} ${robot_action.direction}`);
        
        // 3. Determine if task is complete
        let isComplete = false;
        if (task.action === "move_to") {
          const rx = data.observation.robot_position[0];
          const ry = data.observation.robot_position[1];
          let tx = 0, ty = 0;
          if (task.target === "Delivery Zone") {
            tx = 0; ty = 0;
          } else {
            const pkg = data.observation.packages.find((p: any) => p.id === task.target);
            if (pkg) {
              tx = pkg.position[0];
              ty = pkg.position[1];
            }
          }
          if (rx === tx && ry === ty) isComplete = true;
        } else if (task.action === "move") {
          const remainingSteps = (task.steps || 1) - 1;
          if (remainingSteps <= 0) {
            isComplete = true;
          } else {
            const newQueue = [...executionQueue];
            newQueue[0] = { ...task, steps: remainingSteps };
            setExecutionQueue(newQueue);
            setLoading(false);
            return;
          }
        } else {
          isComplete = true;
        }

        if (isComplete) {
          setExecutionQueue(prev => prev.slice(1));
        }
      }
    } catch (err) {
      setError("Failed to process task queue");
      setExecutionQueue([]);
    } finally {
      setLoading(false);
    }
  };

  const addLog = (msg: string) => {
    setLogs(prev => [msg, ...prev].slice(0, 50));
  };

  const resetEpisode = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ options: { task_level: taskLevel } }),
      });
      const data = await res.json();
      if (data && data.observation) {
        setObs(data);
        addLog(`[RESET] Started ${taskLevel} episode`);
      } else {
        setError("Invalid response from server on reset");
      }
    } catch (err) {
      setError("Failed to connect to backend server at " + API_BASE);
    } finally {
      setLoading(false);
    }
  };

  const runLLMStep = async () => {
    if (!obs || !obs.observation || obs.done || !prompt) return;

    setLoading(true);
    setExecutionQueue([]); // Clear existing queue
    try {
      // 1. Get plan from LLM Agent
      const agentRes = await fetch(`${API_BASE}/llm_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      });
      const plan: LLMPlan = await agentRes.json();
      
      setAiReasoning(plan.reasoning);
      if (plan.tasks && plan.tasks.length > 0) {
        setExecutionQueue(plan.tasks);
        addLog(`[LLM] Parsed ${plan.tasks.length} tasks for instruction: "${prompt}"`);
      } else {
        addLog(`[LLM] Could not parse any tasks from prompt.`);
      }
    } catch (err) {
      setError("Failed to step episode via LLM Agent");
    } finally {
      setLoading(false);
    }
  };

  const stepEpisode = async () => {
    if (!obs || !obs.observation || obs.done) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          action: { direction: "none", act: "no_op" } 
        }), 
      });
      const data = await res.json();
      if (data && data.observation) {
        setObs(data);
        addLog(`[STEP] ${data.observation.message}`);
      } else {
        setError("Invalid response from server on step");
      }
    } catch (err) {
      setError("Failed to step episode");
    } finally {
      setLoading(false);
    }
  };

  const runAutoStep = async () => {
    if (!obs || !obs.observation || obs.done) return;

    setLoading(true);
    try {
      // 1. Get action from AI Agent
      const agentRes = await fetch(`${API_BASE}/agent_action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const robot_action = await agentRes.json();
      
      if (robot_action.reasoning) setAiReasoning(robot_action.reasoning);
      if (robot_action.target) setAiTarget(robot_action.target);
      
      // 2. Execute that action in the environment
      const res = await fetch(`${API_BASE}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: robot_action }),
      });
      const data = await res.json();
      
      if (data && data.observation) {
        setObs(data);
        addLog(`[AUTO] ${robot_action.act} ${robot_action.direction} -> ${data.observation.message}`);
      } else {
        setError("Invalid response from server on auto step");
      }
    } catch (err) {
      setError("Failed to step episode via AI Agent");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (mounted) {
      resetEpisode();
    }
  }, [taskLevel, mounted]);

  if (!mounted) return null;

  return (
    <div className="flex flex-col h-screen bg-slate-900 text-slate-100 font-sans">
      {/* Header */}
      <header className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800 shadow-lg">
        <div className="flex items-center gap-2">
          <Truck className="text-blue-400" size={24} />
          <h1 className="text-xl font-bold tracking-tight">Smart Warehouse Simulator</h1>
        </div>
        <div className="flex items-center gap-4">
          <select 
            value={taskLevel}
            onChange={(e) => setTaskLevel(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
          <button 
            onClick={resetEpisode}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 px-4 py-1.5 rounded text-sm font-medium transition-colors"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            New Episode
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden">
        {/* 3D Viewport */}
        <div className="flex-1 relative bg-slate-950 w-full h-full">
          <Canvas 
            shadows 
            camera={{ position: [8, 10, 8], fov: 35 }}
            style={{ width: '100%', height: '100%' }}
          >
            <color attach="background" args={["#020617"]} />
            <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
            
            <ambientLight intensity={0.7} />
            <pointLight position={[10, 15, 10]} intensity={1.5} castShadow />
            <directionalLight position={[-5, 8, 5]} intensity={0.8} castShadow />
            
            <Grid 
              infiniteGrid 
              fadeDistance={30} 
              fadeStrength={5} 
              sectionSize={1} 
              sectionColor="#1e293b" 
              cellColor="#334155" 
            />

            {obs && obs.observation && (
              <>
                <Floor gridSize={obs.observation.grid_size} />
                <Robot 
                  position={obs.observation.robot_position} 
                  carrying={obs.observation.carrying_package} 
                  gridSize={obs.observation.grid_size}
                />
                {obs.observation.packages.map((pkg) => (
                  <PackageComponent 
                    key={pkg.id} 
                    pkg={pkg} 
                    gridSize={obs.observation.grid_size} 
                    isTarget={aiTarget === pkg.id}
                  />
                ))}
                {obs.observation.obstacles.map((pos, idx) => (
                  <Obstacle key={idx} pos={pos} gridSize={obs.observation.grid_size} />
                ))}
                <DeliveryZone 
                  gridSize={obs.observation.grid_size} 
                  isTarget={aiTarget === "Delivery Zone" || aiTarget === "0, 0"}
                />
              </>
            )}

            <OrbitControls makeDefault />
          </Canvas>

          {/* Overlay Status */}
          {obs && obs.observation && (
            <div className="absolute top-4 left-4 flex flex-col gap-2 pointer-events-none">
              <div className="bg-slate-900/90 backdrop-blur-md p-5 rounded-xl border border-slate-700 shadow-2xl w-72">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-blue-400 text-[10px] font-black uppercase tracking-[0.2em]">System Metrics</h2>
                  <div className="flex items-center gap-1.5 bg-green-500/10 px-2 py-0.5 rounded-full">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[9px] text-green-500 font-bold uppercase tracking-tighter">Live</span>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between items-end border-b border-slate-800 pb-3">
                    <p className="text-slate-500 text-[10px] uppercase font-bold tracking-widest">Total Reward</p>
                    <p className={`text-2xl font-mono leading-none ${(obs.observation.reward ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {(obs.observation.reward ?? 0).toFixed(1)}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                      <p className="text-slate-500 text-[9px] uppercase font-bold mb-1">Delivered</p>
                      <p className="text-lg font-mono text-emerald-400">
                        {obs.observation.delivered_count}<span className="text-slate-600 text-xs mx-0.5">/</span>{obs.observation.total_packages}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                      <p className="text-slate-500 text-[9px] uppercase font-bold mb-1">Steps Left</p>
                      <p className="text-lg font-mono text-blue-400">{obs.observation.steps_remaining}</p>
                    </div>
                  </div>

                  <div className="pt-2">
                    <div className="flex justify-between text-[9px] font-bold text-slate-500 uppercase mb-1.5">
                      <span>Efficiency Index</span>
                      <span className="text-emerald-500">
                        {((obs.observation.delivered_count / Math.max(1, obs.observation.total_packages)) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-emerald-500 transition-all duration-500 ease-out shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                        style={{ width: `${(obs.observation.delivered_count / Math.max(1, obs.observation.total_packages)) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {obs.done && (
                <div className="bg-blue-600/90 backdrop-blur-md p-4 rounded-lg shadow-2xl animate-in zoom-in w-64 text-center">
                  <h3 className="font-bold text-white text-lg">EPISODE COMPLETE</h3>
                  <p className="text-blue-100 text-sm mt-1">
                    Final Score: {(obs.observation.delivered_count / obs.observation.total_packages).toFixed(2)}
                  </p>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="absolute top-4 right-4 bg-red-900/90 border border-red-500 text-red-100 p-4 rounded flex items-center gap-3 shadow-2xl">
              <AlertCircle size={20} />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}
        </div>

        {/* Sidebar Controls & Logs */}
        <aside className="w-96 border-l border-slate-700 bg-slate-800 flex flex-col shadow-2xl z-10">
          <div className="p-4 border-b border-slate-700 bg-slate-900/50">
            <h2 className="text-sm font-bold text-blue-400 uppercase tracking-widest flex items-center gap-2 mb-4">
              <Play size={14} /> AI Control Center
            </h2>

            <div className="mb-4">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2 block">
                LLM Natural Language Instruction
              </label>
              <div className="flex flex-col gap-2">
                <input 
                  type="text" 
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      runLLMStep();
                    }
                  }}
                  placeholder="e.g. Go to shelf A safely"
                  className="bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-100 placeholder:text-slate-600 w-full"
                />
                <button 
                  onClick={runLLMStep}
                  disabled={loading || !obs || obs.done || !prompt}
                  className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 px-4 py-2 rounded text-sm font-bold transition-all shadow-lg active:scale-95"
                >
                  Parse & Execute
                </button>
              </div>
            </div>

            {/* AI Plan Queue */}
            {executionQueue.length > 0 && (
              <div className="mb-4 bg-slate-950/50 rounded-lg border border-slate-700/30 p-3">
                <h3 className="text-[9px] font-black text-blue-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                  <LayoutGrid size={10} /> Active Action Queue
                </h3>
                <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                  {executionQueue.map((task, idx) => (
                    <div 
                      key={idx} 
                      className={`text-[10px] flex items-center justify-between p-1.5 rounded border ${
                        idx === 0 
                        ? "bg-blue-500/20 border-blue-500/50 text-blue-100" 
                        : "bg-slate-900 border-slate-800 text-slate-400"
                      }`}
                    >
                      <span className="font-mono">
                        {idx + 1}. {task.action.toUpperCase()} {task.target || task.direction || ""}
                        {task.steps ? ` (${task.steps} steps)` : ""}
                      </span>
                      {idx === 0 && <span className="text-[8px] animate-pulse font-black uppercase">Executing</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Reasoning Panel */}
            <div className="mb-4 bg-slate-950/80 rounded-lg border border-slate-700/50 p-3 shadow-inner">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-[10px] font-black text-amber-400 uppercase tracking-widest flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
                  AI Reasoning
                </h3>
                {aiTarget && (
                  <span className="text-[9px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-300 font-mono">Target: {aiTarget}</span>
                )}
              </div>
              <div className="text-[11px] font-mono text-slate-300 leading-relaxed min-h-[40px]">
                {aiReasoning ? (
                  <span className="text-slate-200">{aiReasoning}</span>
                ) : (
                  <span className="text-slate-600 italic">Awaiting instructions...</span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <button 
                onClick={() => setIsAutoPlaying(!isAutoPlaying)}
                disabled={loading || !obs || obs.done}
                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-black uppercase tracking-widest transition-all shadow-xl active:scale-95 ${
                  isAutoPlaying 
                  ? "bg-red-600 hover:bg-red-500 animate-glow" 
                  : "bg-emerald-600 hover:bg-emerald-500"
                }`}
              >
                {isAutoPlaying ? "Stop Auto Pilot" : "Start Auto Pilot"}
              </button>

              <div className="grid grid-cols-2 gap-2 mt-2">
                <button 
                  onClick={runAutoStep}
                  disabled={loading || !obs || obs.done || isAutoPlaying}
                  className="flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 px-3 py-2 rounded text-[10px] font-bold transition-all"
                >
                  Step AI Once
                </button>
                <div className="flex flex-col justify-center px-2">
                  <label className="text-[9px] font-bold text-slate-500 uppercase flex justify-between">
                    <span>Speed</span>
                    <span>{autoSpeed}ms</span>
                  </label>
                  <input 
                    type="range" 
                    min="100" 
                    max="1500" 
                    step="100"
                    value={autoSpeed}
                    onChange={(e) => setAutoSpeed(Number(e.target.value))}
                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer mt-1"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-0 bg-slate-900">
            <div className="p-3 border-b border-slate-800 bg-slate-800/80">
              <div className="flex justify-between items-center">
                <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
                  <LayoutGrid size={12} /> Execution Logs
                </h2>
                <label className="flex items-center gap-2 cursor-pointer">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Debug View</span>
                  <input 
                    type="checkbox" 
                    checked={showDebug} 
                    onChange={(e) => setShowDebug(e.target.checked)} 
                    className="w-3 h-3 accent-blue-500 bg-slate-700 border-slate-600 rounded"
                  />
                </label>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-[10px] sm:text-[11px]">
              {logs.map((log, i) => (
                <div key={i} className={`pb-2 border-b border-slate-800/50 ${i === 0 ? "text-blue-300" : "text-slate-500"} ${!showDebug && log.includes('AUTO') ? 'hidden' : ''}`}>
                  <span className="text-slate-600 mr-2">{new Date().toLocaleTimeString([], { hour12: false })}</span>
                  {log}
                </div>
              ))}
              {logs.length === 0 && <p className="text-slate-600 italic">No logs yet...</p>}
            </div>
          </div>

          <div className="p-3 bg-slate-950 border-t border-slate-800 flex justify-between items-center">
            <div className="flex items-center gap-2 text-slate-400">
              <div className={`w-1.5 h-1.5 rounded-full ${obs ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" : "bg-red-500"}`} />
              <span className="text-[9px] font-bold uppercase tracking-widest">
                {obs ? "Backend Sync: OK" : "Backend Offline"}
              </span>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

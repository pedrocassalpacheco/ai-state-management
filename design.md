# AI State Management - System Design

## Deployment Architecture

This system uses **TiDB**, a distributed, MySQL-compatible database with horizontal scalability and ACID guarantees, ideal for managing AI conversation state across multiple users.

### Infrastructure Components

```
┌─────────────────────────────────────────────────────────────────┐
│                       Application Layer                          │
│                  (FastAPI/Express/Bot Framework)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ MySQL Protocol
                             │ Port 3306
                             ▼
                ┌────────────────────────┐
                │   HAProxy (Load Bal.)  │
                │   - Round-robin        │
                │   - Health checks      │
                │   - Automatic failover │
                └────────┬───────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌────────┐       ┌────────┐       ┌────────┐
   │ TiDB 0 │       │ TiDB 1 │       │ TiDB 2 │   Stateless SQL Layer
   │ :4000  │       │ :4001  │       │ :4002  │   (MySQL Compatible)
   └────┬───┘       └────┬───┘       └────┬───┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         │ gRPC
                         ▼
           ┌──────────────────────────┐
           │   PD Cluster (3 nodes)   │        Placement Driver
           │   - Metadata management  │        (Cluster Coordination)
           │   - Timestamp oracle     │
           │   - Region scheduling    │
           └──────────┬───────────────┘
                      │
                      │ Cluster Management
                      ▼
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌────────┐    ┌────────┐    ┌────────┐
   │ TiKV 0 │    │ TiKV 1 │    │ TiKV 2 │      Distributed Storage
   │:20160  │    │:20161  │    │:20162  │      (Key-Value Store)
   └────────┘    └────────┘    └────────┘      • Data persistence
                                                • Raft consensus
                                                • Auto-replication
```

### Component Responsibilities

#### **HAProxy (Load Balancer)**
- **Port:** 3306 (MySQL protocol), 8080 (stats page)
- **Purpose:** Single entry point for all database connections
- **Features:**
  - Round-robin connection distribution
  - Health checks every 2 seconds
  - Automatic failover if TiDB instance fails
  - Session persistence (optional)

#### **TiDB Servers (3 instances)**
- **Ports:** 4000, 4001, 4002
- **Purpose:** Stateless SQL layer, MySQL-compatible interface
- **Characteristics:**
  - All instances access same data (via TiKV)
  - Can scale horizontally by adding more instances
  - No data stored locally (compute-only)
  - Handle SQL parsing, optimization, execution

#### **PD (Placement Driver) Cluster (3 instances)**
- **Ports:** 2379-2384 (client and peer communication)
- **Purpose:** Cluster metadata and coordination
- **Responsibilities:**
  - Store cluster metadata and topology
  - Generate globally unique timestamps
  - Schedule data placement across TiKV
  - Monitor cluster health
  - Handle region splitting and merging

#### **TiKV Storage Cluster (3 instances)**
- **Ports:** 20160-20162
- **Purpose:** Distributed transactional key-value storage
- **Features:**
  - Data persistence layer
  - Raft consensus for replication (3 replicas default)
  - Automatic data sharding (regions)
  - ACID transaction support
  - Multi-version concurrency control (MVCC)

### Data Flow

1. **Write Operation:**
   ```
   Application → HAProxy → TiDB (any instance) → TiKV Leader → 
   Raft Replication to TiKV Followers → Commit Success
   ```

2. **Read Operation:**
   ```
   Application → HAProxy → TiDB (any instance) → TiKV (any replica) → 
   Return Data
   ```

3. **Memory Snapshot with Vector Search:**
   ```
   Application → Generate Embedding → Store in memory_snapshots table
   → TiDB distributes to TiKV → Data replicated across cluster
   
   Query: Application → HAProxy → TiDB → TiKV retrieves matching vectors
   → Return similar memories
   ```

### High Availability Features

- **No Single Point of Failure:**
  - 3 PD nodes (quorum-based)
  - 3 TiKV nodes (Raft replication)
  - 3 TiDB nodes (stateless, any can handle requests)

- **Automatic Failover:**
  - TiDB instance down → HAProxy redirects to healthy instances
  - TiKV node down → Raft elects new leader, continues serving
  - PD node down → Remaining nodes form quorum

- **Data Durability:**
  - Data replicated 3x by default (Raft)
  - Survives loss of 1 TiKV node without data loss
  - Persistent storage via Docker volumes

### Scalability

**Horizontal Scaling:**
- Add more TiDB instances for increased query throughput
- Add more TiKV instances for increased storage capacity
- No downtime required for scaling operations

**Capacity:**
- Supports petabyte-scale data (TiKV)
- Handles millions of concurrent connections (TiDB + HAProxy)
- Suitable for multi-tenant AI applications

### Connection Configuration

**For Applications:**
```python
# Single connection point (recommended)
db_config = {
    'host': '127.0.0.1',
    'port': 3306,        # HAProxy
    'user': 'root',
    'database': 'ai_memory'
}

# Connection pool for HA
pool = create_pool(
    host='127.0.0.1',
    port=3306,
    max_connections=100,
    retry_on_timeout=True
)
```

**For Development/Debugging:**
```bash
# Through load balancer (recommended)
mysql -h 127.0.0.1 -P 3306 -u root

# Direct to specific TiDB instance
mysql -h 127.0.0.1 -P 4000 -u root  # tidb0
mysql -h 127.0.0.1 -P 4001 -u root  # tidb1
mysql -h 127.0.0.1 -P 4002 -u root  # tidb2
```

### Monitoring & Observability

- **HAProxy Stats:** http://localhost:8080
  - Connection distribution
  - Backend health status
  - Request rates and error counts

- **TiDB Dashboard:** http://localhost:2333
  - Cluster topology
  - Query performance metrics
  - Storage capacity and distribution
  - Slow query log

### Production Considerations

**For Production Deployment:**

1. **Persistent Volumes:** Replace Docker volumes with dedicated storage
2. **Resource Limits:** Set appropriate CPU/memory limits per component
3. **Networking:** Use overlay network in Docker Swarm or Kubernetes
4. **Monitoring:** Add Prometheus + Grafana for metrics
5. **Backups:** Implement regular TiKV snapshots (Backup & Restore tool)
6. **Security:** 
   - Enable TLS for all connections
   - Set proper user authentication
   - Network isolation for internal components
7. **Configuration Tuning:**
   - TiKV block cache size (memory)
   - TiDB prepared statement cache
   - HAProxy connection limits

---

## Application Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│              (FastAPI/Express/etc.)                      │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │   TiDB Cluster      │
          │   via HAProxy       │
          │                     │
          │  Hybrid Storage:    │
          │  - Relational Data  │
          │  - JSON Metadata    │
          │  - Vector Embeddings│
          └─────────────────────┘
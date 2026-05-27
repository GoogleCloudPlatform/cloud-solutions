#!/bin/bash
# ==============================================================================
# Oracle 19c Automated Setup Script - PRODUCTION STABLE
# ==============================================================================
set -e

# --- CONFIGURATION ---
LOG_FILE="/tmp/install_output.log"
BUCKET=${BUCKET:?"Error: Staging GCS Bucket must be specified via BUCKET environment variable."}
RPM_NAME=${RPM_NAME:-"oracle-database-ee-19c-1.0-1.x86_64.rpm"}
ORACLE_HOME="/opt/oracle/product/19c/dbhome_1"
INTERNAL_IP=$(ip route get 1 | awk '{print $7;exit}')

# Redirect stdout/stderr to local file and stream to remote-exec
exec > >(tee -a "$LOG_FILE") 2>&1

echo "--- STARTING ORACLE CONFIGURATION: $(date) ---"

# --- 0. HELPER: DOWNLOAD FUNCTION ---
download_file() {
  local FILE_NAME=$1
  local DEST=$2
  gcloud storage cp "gs://${BUCKET}/${FILE_NAME}" "$DEST"
}

# --- 1. DISK PREPARATION ---
echo "Step 1: Preparing Data Disk..."
DISK_ID="google-oracle-data"
DATA_DISK_LINK="/dev/disk/by-id/$DISK_ID"

# GCE persistent disks may mount with dynamic alias IDs depending on OS guest agent discovery.
# Polling both the static symlink alias and raw /dev/sdb nodes prevents race conditions on VM boots.
for i in {1..30}; do
  if [ -L "$DATA_DISK_LINK" ]; then
    DATA_DISK=$(readlink -f "$DATA_DISK_LINK")
    echo "Found disk by ID: $DATA_DISK"
    break
  fi
  if [ -b "/dev/sdb" ]; then
    DATA_DISK="/dev/sdb"
    echo "Found disk by device path: $DATA_DISK"
    break
  fi
  echo "Disk not found yet... ($i/30)"
  sleep 2
done

if [ -z "$DATA_DISK" ]; then
  echo "CRITICAL: No data disk found!"
  lsblk
  exit 1
fi

# Detaching existing disk attachments via lazy unmount prevents I/O pipeline blockages on boot cycles.
sudo umount -l /opt/oracle 2>/dev/null || true

echo "Force formatting $DATA_DISK with ext4..."
sudo mkfs.ext4 -m 0 -F "$DATA_DISK"

sudo mkdir -p /opt/oracle
sudo mount -o discard,defaults "$DATA_DISK" /opt/oracle

# --- 2. INSTALL RPMS (CHRONOLOGICAL PRE-REQ HANDLING) ---
echo "Step 2: Installing Oracle Software..."
# Oracle licensing prohibits packaging the database server RPM inside Git repositories.
# Staging the binary in the GCS bucket allows automated, compliant serverless pulling.
download_file "${RPM_NAME}" "/tmp/oracle19c.rpm"

# Utilizing standard, managed OS repositories for prerequisite packages avoids broken url links.
sudo dnf install -y oracle-database-preinstall-19c

# Oracle guest binaries require dedicated ownership blocks. Handled dynamically on GCE mount.
sudo chown -R oracle:oinstall /opt/oracle
sudo chmod -R 775 /opt/oracle

if [ -d "$ORACLE_HOME" ]; then
  sudo rm -rf /opt/oracle/product/19c /opt/oracle/oraInventory
fi

# Fast RPM install bypasses DNF metadata parsing overhead
sudo rpm -ivh /tmp/oracle19c.rpm

# --- 3. CONFIGURE DATABASE ---
echo "Step 3: Running DBCA..."
if [ ! -d "/opt/oracle/oradata/ORCLCDB" ]; then
  sudo /etc/init.d/oracledb_ORCLCDB-19c configure
else
  echo "Database directory ORCLCDB already exists. Starting Oracle database service..."
  sudo /etc/init.d/oracledb_ORCLCDB-19c start || true
fi

# --- 5. NETWORKING (LISTENER & TNS) ---
echo "Step 5: Configuring TNSNames..."
sudo -u oracle bash <<EOH
export ORACLE_HOME=$ORACLE_HOME
cat > \$ORACLE_HOME/network/admin/tnsnames.ora <<ENDF
ORCLCDB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = ${INTERNAL_IP})(PORT = 1521))
    (CONNECT_DATA = (SERVER = DEDICATED) (SERVICE_NAME = ORCLCDB))
  )

ORCLPDB1 =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = ${INTERNAL_IP})(PORT = 1521))
    (CONNECT_DATA = (SERVER = DEDICATED) (SERVICE_NAME = ORCLPDB1))
  )

LISTENER_ORCLCDB =
  (ADDRESS = (PROTOCOL = TCP)(HOST = ${INTERNAL_IP})(PORT = 1521))
ENDF
\$ORACLE_HOME/bin/lsnrctl start || \$ORACLE_HOME/bin/lsnrctl status || true
EOH

# --- 7. BASHRC ENVIRONMENT ---
echo "Step 7: Finalizing Environment..."
cat <<'EOT' | sudo tee -a /home/oracle/.bashrc /home/"${SUDO_USER:-$USER}"/.bashrc
export ORACLE_SID=ORCLCDB
export ORACLE_BASE=/opt/oracle
export ORACLE_HOME=/opt/oracle/product/19c/dbhome_1
export PATH=$ORACLE_HOME/bin:$PATH
EOT

echo "###################################################"
echo "--- INSTALL COMPLETE ---"
echo "###################################################"

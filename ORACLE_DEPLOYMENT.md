# Oracle Always Free deployment

Status: awaiting Oracle account and VM creation. Nothing has been deployed to Oracle.

## Create the account and server

1. Register through https://www.oracle.com/cloud/free/ and complete account verification yourself. Do not share card details, account passwords or verification codes in chat.
2. Choose your home region carefully; Always Free compute must be created there and capacity may be unavailable.
3. In Compute → Instances → Create instance, name it `autoqa` and select an Always Free eligible Ubuntu 24.04 ARM64 image with `VM.Standard.A1.Flex`.
4. Stay within the current total allowance: 2 OCPUs, 12 GB RAM and 200 GB combined boot/block storage. Start with one VM and a 50 GB boot disk. Verify the console's Always Free eligibility and cost before creating it; do not choose a paid shape to work around capacity shortages.
5. Create/select a public subnet and assign a public IP. Initially permit SSH port 22 only from your own public IP. Keep application, database, Redis and broker ports closed publicly.
6. Save the SSH private key securely during creation. Once running, provide the public IP, SSH username (normally `ubuntu` for Ubuntu), and local key-file path. Never paste the private key contents.

## Checks completed locally

Docker registry manifests checked for `linux/arm64`: Python 3.12.10 slim, Node 22.15.0 alpine, PostgreSQL 17.4 alpine, Redis 7.4.2 alpine and Nginx 1.28 alpine all advertise ARM64 images. This verifies base-image availability, not a successful native ARM application build. Build the Python job image on the Oracle VM as well; transferring only the Compose services will leave the broker without its job image.

## Deployment work after SSH is available

- Verify the server identity and ARM architecture; install Docker Engine and Compose using Docker's official Ubuntu repository.
- Transfer the current application source without `.env`, `.venv`, `node_modules`, `.git`, logs, test data or local database files. Configure cloud secrets separately.
- Use new database credentials and separate application/migration privileges. Do not reuse the development PostgreSQL password.
- Build `autoagent-python:local` from `sandbox/`, then build the application containers natively. Start with one API and one worker and verify memory use.
- Keep the initial installation private via SSH forwarding while testing. Do not expose the Docker socket, broker, PostgreSQL or Redis.
- Configure a stable HTTPS hostname, TLS termination, exact `ALLOWED_ORIGINS`, Supabase Site URL and redirect URLs, plus SMTP before public use.
- Verify signup, login, saved-task recovery, research citations, PDF/MD/DOCX generation, deletion, follow-ups and Python approval/isolation.
- Set up off-host database AND artifact backups and test restoration. Oracle may reclaim idle Always Free instances.

The current trusted sandbox broker controls the host Docker daemon. A public multi-tenant release needs a separate sandbox host or a reviewed alternative isolation boundary. Single-VM deployment is a private beta, not a high-availability production service.

Existing tasks and files stay on the local computer until a deliberate database-and-artifact migration is performed. Supabase Auth identities remain in the existing project. Hosting does not remove model/search/email provider quotas.

## Official references

- Free resources and current limits: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Instance creation: https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm
- Docker on Ubuntu ARM64: https://docs.docker.com/engine/install/ubuntu/

# asset-management
This tool is to manage several assets such as stock, bond, and so on.

## Assumption
I assume that host environment is satisfied with the following conditions.

| Name | Detail |
| :--- | :--- |
| Device | Raspberry Pi 3 model B |
| Architecture | armvl7 (32-bit) |
| OS | Raspbian GNU/Linux 10 (buster) |

But because of using docker environment, you can use the other architecture such as amd64, arm64v8, i386 etc.

## Preparation
1. Install `git`, `docker`, and `docker-compose` to your pc and enable each service.
1. Run the following command and change current directory to this project.

    ```bash
    git clone https://github.com/tnakagami/asset-management.git
    ```

1. Create `.env` files by following markdown files.

    | Target | Path | Detail |
    | :--- | :--- | :--- |
    | postgres | `./env_files/postgres/.env` | [`README.md`](./env_files/postgres/README.md) |
    | backend | `./env_files/backend/.env` | [`README.md`](./env_files/backend/README.md) |

1. Create `.env` file in the top directory of current project. The `.env` file consists of three environment variables.

    | Environment variable | Example | Enables (option) |
    | :--- | :--- | :--- |
    | `ASSETMGMT_ACCESS_PORT` | 3101 | from 1025 to 65535 |
    | `ASSETMGMT_ARCH` | arm32v7 | amd64, arm32v5, arm32v6, arm32v7, arm64v8, i386, mips64le, ppc64le, riscv64, s390x |
    | `ASSETMGMT_TZ` | UTC | UTC, Asia/Tokyo, etc. |

    Please see [`env.sample`](./env.sample) for details.

1. Run the following command to create docker images.

    ```bash
    ./wrapper.sh build
    # or docker-compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
    ```

1. Check [`README.md`](./backend/README.md) to initialize backend application.

## Execution
1. Type the following command, and then wait for a moment.

    ```bash
    ./wrapper.sh start
    # or docker-compose up -d
    ```

1. Access to `http://your-server-ip-address:your-port-number`.

    The default port number is 3101.

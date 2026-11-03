/**
 * @file arm_simulation_interface.cpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief AgileX Piper robotic arm communication and packet parser.
 * @version 0.1
 * @date 2025-05-05
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#include <iostream>
#include <cstdint>
#include <cerrno>
#include <cstring>
#include <unistd.h>
#include <log.hpp>
#include <arm_interface.h>
#include <arm_simulation_interface.h>

void ArmSimulationInterface::start(const char* mujoco_file_path)
{
    this->render_thread_ = std::thread([this]() {
        mjvCamera cam;
        mjv_defaultCamera(&cam);

        mjvOption opt;
        mjv_defaultOption(&opt);

        mjvPerturb pert;
        mjv_defaultPerturb(&pert);

        {
            std::lock_guard<std::mutex> lock(this->sim_mutex_);
            this->sim_ = std::make_unique<mujoco::Simulate>(
                std::make_unique<mujoco::GlfwAdapter>(),
                &cam, &opt, &pert, false
            );
            this->sim_ready_ = true;
        }

        this->sim_ready_cv_.notify_one();

        this->sim_->RenderLoop();
    });

    // Wait until sim_ is ready
    {
        std::unique_lock<std::mutex> lock(this->sim_mutex_);
        this->sim_ready_cv_.wait(lock, [this] { return this->sim_ready_; });
    }

    this->physics_thread_ = std::thread(&ArmSimulationInterface::threadPhysics, this, mujoco_file_path);
    
    // Wait until mujoco model and mujoco data is ready
    {
        std::unique_lock<std::mutex> lock(this->model_mutex_);
        this->model_ready_cv_.wait(lock, [this] { return this->model_ready_; });
    }
}

void ArmSimulationInterface::stop()
{
    this->sim_->exitrequest.store(1);
    this->render_thread_.join();
    this->physics_thread_.join();
}

void ArmSimulationInterface::setLeftJointControl(
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque)
{
    std::lock_guard(this->left_arm_mutex_);
    this->left_arm_target_state_.joint_pos = joint_pos;
    this->left_arm_target_state_.joint_vel = joint_vel;
    this->left_arm_target_state_.joint_torq = joint_feedforward_torque;
}

void ArmSimulationInterface::setRightJointControl(
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_pos,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_vel,
    const Eigen::Vector<double,ArmModel::num_dof_>& joint_feedforward_torque)
{
    std::lock_guard(this->right_arm_mutex_);
    this->right_arm_target_state_.joint_pos = joint_pos;
    this->right_arm_target_state_.joint_vel = joint_vel;
    this->right_arm_target_state_.joint_torq = joint_feedforward_torque;
}

void ArmSimulationInterface::setLeftGripperControl(const double& position, const double& torque)
{
    /* @todo Add position/torque control logic */
    this->d->ctrl[6] = position/2.0;
    this->d->ctrl[7] = -position/2.0;
}

void ArmSimulationInterface::setRightGripperControl(const double& position, const double& torque)
{
    /* @todo Add position/torque control logic */
    this->d->ctrl[14] = position/2.0;
    this->d->ctrl[15] = -position/2.0;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getLeftJointPosition()
{
    std::lock_guard<std::mutex> lock(this->left_arm_mutex_);
    return this->left_arm_target_state_.joint_pos;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getLeftJointVelocity()
{
    std::lock_guard<std::mutex> lock(this->left_arm_mutex_);
    return this->left_arm_target_state_.joint_vel;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getLeftJointAcceleration()
{
    std::lock_guard<std::mutex> lock(this->left_arm_mutex_);
    return this->left_arm_target_state_.joint_acc;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getLeftJointTorque()
{
    std::lock_guard<std::mutex> lock(this->left_arm_mutex_);
    return this->left_arm_target_state_.joint_torq;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getRightJointPosition()
{
    std::lock_guard<std::mutex> lock(this->right_arm_mutex_);
    return this->right_arm_target_state_.joint_pos;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getRightJointVelocity()
{
    std::lock_guard<std::mutex> lock(this->right_arm_mutex_);
    return this->right_arm_target_state_.joint_vel;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getRightJointAcceleration()
{
    std::lock_guard<std::mutex> lock(this->right_arm_mutex_);
    return this->right_arm_target_state_.joint_acc;
}

const Eigen::Vector<double,ArmModel::num_dof_>& ArmSimulationInterface::getRightJointTorque()
{
    std::lock_guard<std::mutex> lock(this->right_arm_mutex_);
    return this->right_arm_target_state_.joint_torq;
}

void ArmSimulationInterface::setLeftMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation)
{
    this->d->mocap_pos[0] = position(0);
    this->d->mocap_pos[1] = position(1);
    this->d->mocap_pos[2] = position(2);

    this->d->mocap_quat[0] = orientation.w();
    this->d->mocap_quat[1] = orientation.x();
    this->d->mocap_quat[2] = orientation.y();
    this->d->mocap_quat[3] = orientation.z();
}

void ArmSimulationInterface::setRightMocapPose(const Eigen::Vector3d& position, const Eigen::Quaterniond& orientation)
{
    this->d->mocap_pos[3] = position(0);
    this->d->mocap_pos[4] = position(1);
    this->d->mocap_pos[5] = position(2);

    this->d->mocap_quat[4] = orientation.w();
    this->d->mocap_quat[5] = orientation.x();
    this->d->mocap_quat[6] = orientation.y();
    this->d->mocap_quat[7] = orientation.z();
}

void ArmSimulationInterface::setJointPDControl()
{
    Eigen::Vector<double, ArmModel::num_dof_> left_control =
        this->joint_kp_ * (this->left_arm_target_state_.joint_pos - this->left_arm_actual_state_.joint_pos) + 
        this->joint_kd_ * (this->left_arm_target_state_.joint_vel - this->left_arm_actual_state_.joint_vel) +
        this->left_arm_target_state_.joint_torq;
    Eigen::Vector<double, ArmModel::num_dof_> right_control =
        this->joint_kp_ * (this->right_arm_target_state_.joint_pos - this->right_arm_actual_state_.joint_pos) + 
        this->joint_kd_ * (this->right_arm_target_state_.joint_vel - this->right_arm_actual_state_.joint_vel) +
        this->right_arm_target_state_.joint_torq;

    for ( int i=0 ; i<ArmModel::num_dof_ ; i++ )
    {
        this->d->ctrl[i] = left_control[i];
        this->d->ctrl[i+ArmModel::num_dof_+1] = right_control[i]; // +1 for left gripper joint
    }
    LOG_DEBUG("Left arm target joint position:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->left_arm_target_state_.joint_pos(0),this->left_arm_target_state_.joint_pos(1),this->left_arm_target_state_.joint_pos(2),
        this->left_arm_target_state_.joint_pos(3),this->left_arm_target_state_.joint_pos(4),this->left_arm_target_state_.joint_pos(5));
    LOG_DEBUG("Left arm actual joint position:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->left_arm_actual_state_.joint_pos(0),this->left_arm_actual_state_.joint_pos(1),this->left_arm_actual_state_.joint_pos(2),
        this->left_arm_actual_state_.joint_pos(3),this->left_arm_actual_state_.joint_pos(4),this->left_arm_actual_state_.joint_pos(5));
    LOG_DEBUG("Left arm feedforward torque:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->left_arm_target_state_.joint_torq(0),this->left_arm_target_state_.joint_torq(1),this->left_arm_target_state_.joint_torq(2),
        this->left_arm_target_state_.joint_torq(3),this->left_arm_target_state_.joint_torq(4),this->left_arm_target_state_.joint_torq(5));
    LOG_DEBUG("Mujoco set left arm joint torque:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        left_control(0),left_control(1),left_control(2),left_control(3),left_control(4),left_control(5));

    LOG_DEBUG("Right arm target joint position:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->right_arm_target_state_.joint_pos(0),this->right_arm_target_state_.joint_pos(1),this->right_arm_target_state_.joint_pos(2),
        this->right_arm_target_state_.joint_pos(3),this->right_arm_target_state_.joint_pos(4),this->right_arm_target_state_.joint_pos(5));
    LOG_DEBUG("Right arm actual joint position:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->right_arm_actual_state_.joint_pos(0),this->right_arm_actual_state_.joint_pos(1),this->right_arm_actual_state_.joint_pos(2),
        this->right_arm_actual_state_.joint_pos(3),this->right_arm_actual_state_.joint_pos(4),this->right_arm_actual_state_.joint_pos(5));
    LOG_DEBUG("Right arm feedforward torque:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        this->right_arm_target_state_.joint_torq(0),this->right_arm_target_state_.joint_torq(1),this->right_arm_target_state_.joint_torq(2),
        this->right_arm_target_state_.joint_torq(3),this->right_arm_target_state_.joint_torq(4),this->right_arm_target_state_.joint_torq(5));
    LOG_DEBUG("Mujoco set right arm joint torque:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
        right_control(0),right_control(1),right_control(2),right_control(3),right_control(4),right_control(5));
}

const char* ArmSimulationInterface::diverged(int disableflags, const mjData* d) {
    if (disableflags & mjDSBL_AUTORESET) {
        for (mjtWarning w : {mjWARN_BADQACC, mjWARN_BADQVEL, mjWARN_BADQPOS}) {
            if (d->warning[w].number > 0) {
                return mju_warningText(w, d->warning[w].lastinfo);
            }
        }
    }
    return nullptr;
}

mjModel* ArmSimulationInterface::loadModel(const char* file)
{
    // this copy is needed so that the mujoco::sample_util::strlen call below compiles
    char filename[mujoco::Simulate::kMaxFilenameLength];
    mujoco::sample_util::strcpy_arr(filename, file);

    // make sure filename is not empty
    if (!filename[0]) {
        return nullptr;
    }

    // load and compile
    char loadError[kErrorLength] = "";
    mjModel* mnew = 0;
    auto load_start = mujoco::Simulate::Clock::now();
    if (mujoco::sample_util::strlen_arr(filename)>4 &&
        !std::strncmp(filename + mujoco::sample_util::strlen_arr(filename) - 4, ".mjb", mujoco::sample_util::sizeof_arr(filename) - mujoco::sample_util::strlen_arr(filename)+4)) {
        mnew = mj_loadModel(filename, nullptr);
        if (!mnew) {
            mujoco::sample_util::strcpy_arr(loadError, "could not load binary model");
        }
    } else {
        mnew = mj_loadXML(filename, nullptr, loadError, kErrorLength);

        // remove trailing newline character from loadError
        if (loadError[0]) {
            int error_length = mujoco::sample_util::strlen_arr(loadError);
            if (loadError[error_length-1] == '\n') {
                loadError[error_length-1] = '\0';
            }
        }
    }
    auto load_interval = mujoco::Simulate::Clock::now() - load_start;
    double load_seconds = std::chrono::duration<double>(load_interval).count();

    if (!mnew) {
        LOG_ERROR("{}", loadError);
        mujoco::sample_util::strcpy_arr(this->sim_->load_error, loadError);
        return nullptr;
    }

    // compiler warning: print and pause
    if (loadError[0]) {
        // mj_forward() below will print the warning message
        LOG_ERROR("Model compiled, but simulation warning (paused):{}", loadError);
        this->sim_->run = 0;
    }

    // if no error and load took more than 1/4 seconds, report load time
    else if (load_seconds > 0.25) {
        mujoco::sample_util::sprintf_arr(loadError, "Model loaded in %.2g seconds", load_seconds);
    }

    mujoco::sample_util::strcpy_arr(this->sim_->load_error, loadError);

    return mnew;
}

// simulate in background thread (while rendering in main thread)
void ArmSimulationInterface::physicsLoop()
{
    // cpu-sim syncronization point
    std::chrono::time_point<mujoco::Simulate::Clock> syncCPU;
    mjtNum syncSim = 0;

    // run until asked to exit
    while (!this->sim_->exitrequest.load())
    {
        if (this->sim_->droploadrequest.load()) {
            this->sim_->LoadMessage(this->sim_->dropfilename);
            mjModel* mnew = loadModel(this->sim_->dropfilename);
            this->sim_->droploadrequest.store(false);

            mjData* dnew = nullptr;
            if (mnew) dnew = mj_makeData(mnew);
            if (dnew) {
                this->sim_->Load(mnew, dnew, this->sim_->dropfilename);

                // lock the sim mutex
                const std::unique_lock<std::recursive_mutex> lock(this->sim_->mtx);

                mj_deleteData(d);
                mj_deleteModel(m);

                m = mnew;
                d = dnew;
                mj_forward(m, d);

            } else {
                this->sim_->LoadMessageClear();
            }
        }

        if (this->sim_->uiloadrequest.load()) {
            this->sim_->uiloadrequest.fetch_sub(1);
            this->sim_->LoadMessage(this->sim_->filename);
            mjModel* mnew = loadModel(this->sim_->filename);
            mjData* dnew = nullptr;
            if (mnew) dnew = mj_makeData(mnew);
            if (dnew) {
                this->sim_->Load(mnew, dnew, this->sim_->filename);

                // lock the sim mutex
                const std::unique_lock<std::recursive_mutex> lock(this->sim_->mtx);

                mj_deleteData(d);
                mj_deleteModel(m);

                m = mnew;
                d = dnew;
                mj_forward(m, d);

            } else {
                this->sim_->LoadMessageClear();
            }
        }

        // sleep for 1 ms or yield, to let main thread run
        //  yield results in busy wait - which has better timing but kills battery life
        if (this->sim_->run && this->sim_->busywait) {
            std::this_thread::yield();
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }

        {
            // lock the sim mutex
            const std::unique_lock<std::recursive_mutex> lock(this->sim_->mtx);

            // run only if model is present
            if (m)
            {
                // running
                if (this->sim_->run)
                {
                    bool stepped = false;

                    // record cpu time at start of iteration
                    const auto startCPU = mujoco::Simulate::Clock::now();

                    // elapsed CPU and simulation time since last sync
                    const auto elapsedCPU = startCPU - syncCPU;
                    double elapsedSim = d->time - syncSim;

                    // requested slow-down factor
                    double slowdown = 100 / this->sim_->percentRealTime[this->sim_->real_time_index];

                    // misalignment condition: distance from target sim time is bigger than syncmisalign
                    bool misaligned =
                        std::abs(std::chrono::duration<double>(elapsedCPU).count()/slowdown - elapsedSim) > syncMisalign;

                    // out-of-sync (for any reason): reset sync times, step
                    if (elapsedSim < 0 || elapsedCPU.count() < 0 || syncCPU.time_since_epoch().count() == 0 || misaligned || this->sim_->speed_changed)
                    {
                        // re-sync
                        syncCPU = startCPU;
                        syncSim = d->time;
                        this->sim_->speed_changed = false;

                        // run single step, let next iteration deal with timing
                        for ( int i=0 ; i<ArmModel::num_dof_ ; i++ )
                        {
                            this->left_arm_actual_state_.joint_pos(i) = this->d->qpos[i];
                            this->right_arm_actual_state_.joint_pos(i) = this->d->qpos[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                            this->left_arm_actual_state_.joint_vel(i) = this->d->qvel[i];
                            this->right_arm_actual_state_.joint_vel(i) = this->d->qvel[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                            this->left_arm_actual_state_.joint_acc(i) = this->d->qacc[i];
                            this->right_arm_actual_state_.joint_acc(i) = this->d->qacc[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                            this->left_arm_actual_state_.joint_torq(i) = this->d->qfrc_actuator[i];
                            this->right_arm_actual_state_.joint_torq(i) = this->d->qfrc_actuator[i+ArmModel::num_dof_+2]; // +2 to skip left gripper joint
                        }
                        mj_step1(m, d);
                        /* Apply joint level PD control logic to mujoco model.
                         * This operation is only valid with "assets/mujoco_model/piper_dual_arm_torque.xml" */
                        // this->setJointPDControl();

                        /* Set position command to mujoco model.
                         * This operation only valid with "assets/mujoco_model/piper_dual_arm_position.xml" */
                        for ( std::size_t i=0 ; i<ArmModel::num_dof_ ; i++ )
                        {
                            this->d->ctrl[i] = this->left_arm_target_state_.joint_pos(i);
                            this->d->ctrl[i+2+ArmModel::num_dof_] = this->right_arm_target_state_.joint_pos(i);
                        }
                        // LOG_DEBUG("Set left arm joint position in mujoco:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                        //     this->left_arm_target_state_.joint_pos(0),this->left_arm_target_state_.joint_pos(1),this->left_arm_target_state_.joint_pos(2),
                        //     this->left_arm_target_state_.joint_pos(3),this->left_arm_target_state_.joint_pos(4),this->left_arm_target_state_.joint_pos(5));
                        // LOG_DEBUG("Set right arm joint position in mujoco:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                        //     this->right_arm_target_state_.joint_pos(0),this->right_arm_target_state_.joint_pos(1),this->right_arm_target_state_.joint_pos(2),
                        //     this->right_arm_target_state_.joint_pos(3),this->right_arm_target_state_.joint_pos(4),this->right_arm_target_state_.joint_pos(5));
                        mj_step2(m, d);
                        const char* message = diverged(m->opt.disableflags, d);
                        if (message)
                        {
                            this->sim_->run = 0;
                            mujoco::sample_util::strcpy_arr(this->sim_->load_error, message);
                        }
                        else
                        {
                            stepped = true;
                        }
                    }

                    // in-sync: step until ahead of cpu
                    else
                    {
                        bool measured = false;
                        mjtNum prevSim = d->time;

                        double refreshTime = simRefreshFraction/this->sim_->refresh_rate;

                        // step while sim lags behind cpu and within refreshTime
                        while (std::chrono::duration<double>((d->time - syncSim)*slowdown) < mujoco::Simulate::Clock::now() - syncCPU &&
                            mujoco::Simulate::Clock::now() - startCPU < std::chrono::duration<double>(refreshTime))
                        {
                            // measure slowdown before first step
                            if (!measured && elapsedSim)
                            {
                                this->sim_->measured_slowdown =
                                    std::chrono::duration<double>(elapsedCPU).count() / elapsedSim;
                                measured = true;
                            }

                            // inject noise
                            this->sim_->InjectNoise();

                            // call mj_step
                            for ( int i=0 ; i<ArmModel::num_dof_ ; i++ )
                            {
                                this->left_arm_actual_state_.joint_pos(i) = this->d->qpos[i];
                                this->right_arm_actual_state_.joint_pos(i) = this->d->qpos[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                                this->left_arm_actual_state_.joint_vel(i) = this->d->qvel[i];
                                this->right_arm_actual_state_.joint_vel(i) = this->d->qvel[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                                this->left_arm_actual_state_.joint_acc(i) = this->d->qacc[i];
                                this->right_arm_actual_state_.joint_acc(i) = this->d->qacc[i+ArmModel::num_dof_+2];  // +2 to skip left gripper joint
                                this->left_arm_actual_state_.joint_torq(i) = this->d->qfrc_actuator[i];
                                this->right_arm_actual_state_.joint_torq(i) = this->d->qfrc_actuator[i+ArmModel::num_dof_+2]; // +2 to skip left gripper joint
                            }
                            mj_step1(m, d);
                            /* Apply joint level PD control logic to mujoco model.
                            * This operation is only valid with "assets/mujoco_model/piper_dual_arm_torque.xml" */
                            // this->setJointPDControl();

                            /* Set position command to mujoco model.
                            * This operation only valid with "assets/mujoco_model/piper_dual_arm_position.xml" */
                            for ( std::size_t i=0 ; i<ArmModel::num_dof_ ; i++ )
                            {
                                this->d->ctrl[i] = this->left_arm_target_state_.joint_pos(i);
                                this->d->ctrl[i+2+ArmModel::num_dof_] = this->right_arm_target_state_.joint_pos(i);
                            }
                            // LOG_DEBUG("Set left arm joint position in mujoco:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                            //     this->left_arm_target_state_.joint_pos(0),this->left_arm_target_state_.joint_pos(1),this->left_arm_target_state_.joint_pos(2),
                            //     this->left_arm_target_state_.joint_pos(3),this->left_arm_target_state_.joint_pos(4),this->left_arm_target_state_.joint_pos(5));
                            // LOG_DEBUG("Set right arm joint position in mujoco:{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}",
                            //     this->right_arm_target_state_.joint_pos(0),this->right_arm_target_state_.joint_pos(1),this->right_arm_target_state_.joint_pos(2),
                            //     this->right_arm_target_state_.joint_pos(3),this->right_arm_target_state_.joint_pos(4),this->right_arm_target_state_.joint_pos(5));
                            mj_step2(m, d);
                            const char* message = diverged(m->opt.disableflags, d);
                            if (message)
                            {
                                this->sim_->run = 0;
                                mujoco::sample_util::strcpy_arr(this->sim_->load_error, message);
                            }
                            else
                            {
                                stepped = true;
                            }

                            // break if reset
                            if (d->time < prevSim)
                            {
                                break;
                            }
                        }
                    }

                    // save current state to history buffer
                    if (stepped)
                    {
                        this->sim_->AddToHistory();
                    }
                }

                // paused
                else
                {
                    // run mj_forward, to update rendering and joint sliders
                    mj_forward(m, d);
                    this->sim_->speed_changed = true;
                }
            }
        }  // release std::lock_guard<std::mutex>
    }
}

void ArmSimulationInterface::threadPhysics(const char* mujoco_file_path)
{
    this->sim_->LoadMessage(mujoco_file_path);

    std::unique_lock<std::mutex> lock(this->model_mutex_);

    m = this->loadModel(mujoco_file_path);
    if (m)
    {
      // lock the sim mutex
      const std::unique_lock<std::recursive_mutex> lock(this->sim_->mtx);

      d = mj_makeData(m);
    }
    if (d)
    {
      this->sim_->Load(m, d, mujoco_file_path);

      // lock the this->sim_ mutex
      const std::unique_lock<std::recursive_mutex> lock(this->sim_->mtx);

      mj_forward(m, d);

    }
    else
    {
      this->sim_->LoadMessageClear();
    }

    lock.unlock();

    this->model_ready_cv_.notify_one();
    this->model_ready_ = true;

    this->physicsLoop();

    // delete everything we allocated
    mj_deleteData(d);
    mj_deleteModel(m);
}
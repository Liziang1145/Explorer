if (~exist("robot", "var"))
    load_robot();
end

link(1) = Link([0 0.123 0 0], "modified");
link(2) = Link([0 0 0 -pi/2], "modified");
link(3) = Link([0 0 0.28503 0], "modified");
link(4) = Link([0 0.25075 -0.02198 pi/2], "modified");
link(5) = Link([0 0 0 -pi/2], "modified");
link(6) = Link([0 0.091 0 pi/2], "modified");

% create serial link robot
serialrbt = SerialLink(link, "name", "piper");

joint_pos = zeros(6,1);

for c=1:100
    fprintf("iteration:%d/100\n",c);
    joint_pos(1:robot.num_dof,1) = robot.joint_limit(1:robot.num_dof,1) + (robot.joint_limit(1:robot.num_dof,2) - robot.joint_limit(1:robot.num_dof,1)).*rand(robot.num_dof,1);

    [link_transform,link_com_transform] = getTransforms(robot,joint_pos);
    pose = link_transform(1:4,1:4,6);
    % disp("URDF pose:");
    % disp(link_transform(1:4,1:4,6));
    
    % pose = serialrbt.fkine(joint_pos + [0;-172.22/180*pi;-102.78/180*pi;0;0;0]);
    % pose = [pose.n,pose.o,pose.a,pose.t;0,0,0,1];
    % disp("robotic system toolbox pose:");
    % disp(pose);
    
    % T01 = getMDHTransform(0.123,0,0,joint_pos(1));
    % T12 = getMDHTransform(0,0,-pi/2,joint_pos(2)-172.22/180*pi);
    % T23 = getMDHTransform(0,0.28503,0,joint_pos(3)-102.78/180*pi);
    % T34 = getMDHTransform(0.25075,-0.02198,pi/2,joint_pos(4));
    % T45 = getMDHTransform(0,0,-pi/2,joint_pos(5));
    % T56 = getMDHTransform(0.091,0,pi/2,joint_pos(6));
    % pose = robot.base_transform*T01*T12*T23*T34*T45*T56;
    % disp("MDH pose:");
    % disp(pose);
    try
        possible_joint_pos = getInverseKinematics(robot,pose,joint_pos);
    catch
        disp("no solution");
    end
    if ( all(possible_joint_pos > robot.joint_limit(1:6,1)) && all(possible_joint_pos < robot.joint_limit(1:6,2)) )
        if ( all(abs(joint_pos - possible_joint_pos) < 0.02) )
            disp("pass");
        end
        % T01 = getMDHTransform(0.123,0,0,possible_joint_pos(1));
        % T12 = getMDHTransform(0,0,-pi/2,possible_joint_pos(2)-172.22/180*pi);
        % T23 = getMDHTransform(0,0.28503,0,possible_joint_pos(3)-102.78/180*pi);
        % T34 = getMDHTransform(0.25075,-0.02198,pi/2,possible_joint_pos(4));
        % T45 = getMDHTransform(0,0,-pi/2,possible_joint_pos(5));
        % T56 = getMDHTransform(0.091,0,pi/2,possible_joint_pos(6));
        % possible_pose = robot.base_transform*T01*T12*T23*T34*T45*T56;
        % possible_quat = rotm2quat(possible_pose(1:3,1:3));
        % target_quat = rotm2quat(pose(1:3,1:3));
        % rotation_diff = target_quat - possible_quat;
        % translation_diff = pose(1:3,4) - possible_pose(1:3,4);
        % if ( all(abs(rotation_diff)<1e-3) && norm(translation_diff)<1e-3 )
        %     solution = solution + 1;
        %     % disp(possible_joint_pos(1:6,i)');
        % else
        %     disp("###error: inequal pose from inverse kinematics.");
        % end
    end
end
% serialrbt.plot(joint_pos' + joint_pos_ofs');

function T = getMDHTransform(d,a,alpha,theta)
    T = zeros(4);
    T(1,1) = cos(theta);
    T(1,2) = -sin(theta);
    T(1,4) = a;
    T(2,1) = cos(alpha)*sin(theta);
    T(2,2) = cos(alpha)*cos(theta);
    T(2,3) = -sin(alpha);
    T(2,4) = -d*sin(alpha);
    T(3,1) = sin(alpha)*sin(theta);
    T(3,2) = sin(alpha)*cos(theta);
    T(3,3) = cos(alpha);
    T(3,4) = d*cos(alpha);
    T(4,4) = 1;
end
function best_joint_pos = getInverseKinematics(robot,pose,ref_conf)
    best_joint_pos = [5;5;5;5;5;5];
    joint_pos = zeros(6,8);
    result_count = 1;

    d1 = 0.123;
    alpha2 = -pi/2;
    a3 = 0.28503;
    d4 = 0.25075;
    a4 = -0.02198;
    alpha5 = -pi/2;
    d6 = 0.091;
    alpha6 = pi/2;

    base_transform_inv = [robot.base_transform(1:3,1:3)',-robot.base_transform(1:3,1:3)'*robot.base_transform(1:3,4);0,0,0,1];

    % pose in arm base frame
    pose_base = base_transform_inv * pose;

    % wrist position in arm base frame
    pw0 = pose_base(1:3,4) - d6*pose_base(1:3,3);

    % wrist pose in arm base frame
    pose_wrist_base = [pose_base(1:3,1:3),pw0;0,0,0,1];

    theta1 = zeros(2,1);
    % theta1(1) = atan2(d6*ay+py,d6*ax+px);
    theta1(1) = atan2(pw0(2),pw0(1));
    if ( theta1(1) > 0 )
        theta1(2) = theta1(1) - pi;
    else
        theta1(2) = theta1(1) + pi;
    end
    for i=1:2

        % transform matrix from arm base frame to link 1 frame.
        T01 = [cos(theta1(i)),-sin(theta1(i)),0,0;
               sin(theta1(i)),cos(theta1(i)),0,0;
               0,0,1,d1;
               0,0,0,1];
        T01_inv = [T01(1:3,1:3)',-T01(1:3,1:3)'*T01(1:3,4);0,0,0,1];

        % wrist pose transformation matrix in link 1 frame.
        pose_wrist_1 = T01_inv * pose_wrist_base;

        % x, y, z position of wrist in link 1 frame.
        xw1 = pose_wrist_1(1,4);
        % yw1 = pose_wrist_1(2,4);
        zw1 = pose_wrist_1(3,4);

        % y position of wrist will be zero in theory.
        % if ( yw1 ~= 0 )
        %     fprintf("error: wrist y position in link frame is not 0,y=%f\n",yw1);
        % end

        temp1 = (xw1^2 + zw1^2 - d4^2 -a4^2 + a3^2) / (2*zw1);
        temp2 = xw1/zw1;
        
        delta = temp1^2 * temp2^2 - (1+temp2^2)*(temp1^2-a3^2);
        if ( delta < 0 )
            if (delta>1e-5)
                delta = 0;
            else
                error("Inverse Kinematics No Solution");
            end
        end
        % first possible x position of the origin of link 3 frame expressed in link 1 frame.
        x31_1 = (temp1*temp2 + sqrt(delta)) / (1+temp2^2);

        % second possible x position of the origin of link 3 frame expressed in link 1 frame.
        x31_2 = (temp1*temp2 - sqrt(delta)) / (1+temp2^2);

        % first possible z position of the origin of link 3 frame expressed in link 1 frame.
        z31_1 = temp1 - temp2*x31_1;

        % second possible z position of the origin of link 3 frame expressed in link 1 frame.
        z31_2 = temp1 - temp2*x31_2;

        theta2 = zeros(2,1);
        theta3 = zeros(2,1);

        theta2(1) = -atan2(z31_1,x31_1);
        theta2(2) = -atan2(z31_2,x31_2);
        
        temp1 = atan2(d4,-a4);
        temp2 = acos(max(-1,min(1,(a4^2 + d4^2 + x31_1^2 + z31_1^2 - xw1^2 - zw1^2) / (2 * sqrt(a4^2+d4^2) * sqrt(x31_1^2 + z31_1^2)))));
        temp3 = acos(max(-1,min(1,(a4^2 + d4^2 + x31_2^2 + z31_2^2 - xw1^2 - zw1^2) / (2 * sqrt(a4^2+d4^2) * sqrt(x31_2^2 + z31_2^2)))));
        theta3_1 = - temp1 - temp2;
        theta3_2 = - temp1 - temp3;
        theta3_3 = temp2 - temp1;
        theta3_4 = temp3 - temp1;

        if ( abs(a4*cos(theta2(1)+theta3_1) + d4*sin(theta2(1)+theta3_1) + a3*cos(theta2(1)) - xw1) < 1e-3)
            theta3(1) = theta3_1;
        else
            theta3(1) = theta3_3;
        end

        if ( abs(a4*cos(theta2(2)+theta3_2) + d4*sin(theta2(2)+theta3_2) + a3*cos(theta2(2)) - xw1) < 1e-3)
            theta3(2) = theta3_2;
        else
            theta3(2) = theta3_4;
        end

        if ( theta3(1) > -102.78/180*pi )
            theta3(1) = theta3(1) - 2*pi;
        end
        if ( theta3(2) > -102.78/180*pi )
            theta3(2) = theta3(2) - 2*pi;
        end

        for j=1:2
            R1 = rotz(theta1(i)/pi*180);
            R2 = roty(theta2(j)/pi*180);
            R3 = roty(theta3(j)/pi*180);

            % rotation of wrist (only the last 3 joints, not including first 3 joints)
            R = R3' * R2' * R1' * pose_wrist_base(1:3,1:3);
            
            % disp("wrist rotation:");
            % disp(R);

            theta4 = zeros(2,1);
            theta5 = zeros(2,1);
            theta6 = zeros(2,1);

            theta4(1) = atan2(R(2,3),R(1,3));
            if ( theta4(1) > 0 )
                theta4(2) = theta4(1) - pi;
            else
                theta4(2) = theta4(1) + pi;
            end

            theta5(1) = atan2(sqrt(R(3,1)^2+R(3,2)^2),R(3,3));
            theta5(2) = -theta5(1);

            theta6(1) = atan2(R(3,2),-R(3,1));
            if ( theta6(1) > 0 )
                theta6(2) = theta6(1) - pi;
            else
                theta6(2) = theta6(1) + pi;
            end

            for k=1:2
                joint_pos(1:6,result_count) = [theta1(i);theta2(j)+172.22/180*pi;theta3(j)+102.78/180*pi;theta4(k);theta5(k);theta6(k)];
                result_count = result_count + 1;
            end
        end
    end
    best_id = -1;
    min_movement = 10000;
    for i=1:8
        if ( all(joint_pos(1:6,i) > robot.joint_limit(1:6,1)) && all(joint_pos(1:6,i) < robot.joint_limit(1:6,2)) )
            movement = sum((joint_pos(1:6,i)-ref_conf).^2);
            if ( movement < min_movement )
                min_movement = movement;
                best_id = i;
            end
        end
    end
    if ( best_id == -1 )
        error("Inverse Kinematics No Solution");
    end
    best_joint_pos(1:6,1) = joint_pos(1:6,best_id);
end


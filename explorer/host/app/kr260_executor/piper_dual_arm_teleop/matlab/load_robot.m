
num_link = 7;
num_dof = 6;

link_default_transform = zeros(4,4,num_link);
link_com = zeros(3,num_link);
link_mass = zeros(num_link,1);
link_inertia = zeros(3,3,num_link);
joint_axis = zeros(3,num_link);
joint_type = zeros(num_link,1);
joint_limit = zeros(num_dof,2);

id = 1;
rpy = [0;0;0];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0;0;0.123];
link_com(1:3,id) = [0.000121504734057468; 0.000104632162460536; -0.00438597309559853];
link_mass(id) = 0.71;
link_inertia(1:3,1:3,id) = [ 0.00048916,-0.00000036,-0.00000224;-0.00000036, 0.00040472,-0.00000242;-0.00000224,-0.00000242,0.00043982];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [-2.618,2.618];

id = 2;
rpy = [pi/2;-0.1359;-pi];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0;0;0];
link_com(1:3,id) = [0.198666145229743; -0.010926924140076; 0.00142121714502687];
link_mass(id) = 1.17;
link_inertia(1:3,1:3,id) = [0.00116918,-0.00180037,0.00025146;-0.00180037,0.06785384,-0.00000455;0.00025146,-0.00000455,0.06774489];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [0,3.1415926];

id = 3;
rpy = [0;0;-1.7939];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0.28503;0;0];
link_com(1:3,id) = [-0.0202737662122021; -0.133914995944595; -0.000458682652737356];
link_mass(id) = 0.5;
link_inertia(1:3,1:3,id) = [0.01361711,0.00165794,-0.00000048;0.00165794,0.00045024,-0.00000045;-0.00000048,-0.00000045,0.01380322];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [-2.967,0];

id = 4;
rpy = [pi/2;0;0];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [-0.021984;-0.25075;0];
link_com(1:3,id) = [-9.66635791618542E-05; 0.000876064475651083; -0.00496880904640868];
link_mass(id) = 0.38;
link_inertia(1:3,1:3,id) = [0.00018501,0.00000054,0.00000120;0.00000054,0.00018965,-0.00000841;0.00000120,-0.00000841,0.00015484];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [-1.745,1.745];

id = 5;
rpy = [-pi/2;0;0];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0;0;0];
link_com(1:3,id) = [-4.10554118924211E-05; -0.0566486692356075; -0.0037205791677906];
link_mass(id) = 0.383;
link_inertia(1:3,1:3,id) = [0.00166169,0.00000006,-0.00000007;0.00000006,0.00018510,0.00001026;-0.00000007,0.00001026,0.00164321];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [-1.22,1.22];

id = 6;
rpy = [pi/2;0;0];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0; -0.091; 0];
link_com(1:3,id) = [-8.82590762930069E-05; 9.0598378529832E-06; -0.002];
link_mass(id) = 0.007;
link_inertia(1:3,1:3,id) = [5.73015540542155E-07,-1.98305403089247E-22,-7.2791893904596E-23;-1.98305403089247E-22,5.73015540542155E-07,-3.4146026640245E-24;-7.2791893904596E-23,-3.4146026640245E-24,1.06738869138926E-06];
joint_axis(1:3,id) = [0;0;1];
joint_type(id) = JointType.REVOLUTE;
joint_limit(id,1:2) = [-2.0944,2.0944];

id = 7;
rpy = [0;0;0];
link_default_transform(1:4,1:4,id) = eye(4);
link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
link_default_transform(1:3,4,id) = [0;0;0];
link_com(1:3,id) = [-0.000183807162235591; 8.05033155577911E-05; 0.0321436689908876];
link_mass(id) = 0.45;
link_inertia(1:3,1:3,id) = [0.00092934,0.00000034,-0.00000738;0.00000034,0.00071447,0.00000005;-0.00000738,0.00000005,0.00039442];
joint_axis(1:3,id) = [0;0;0];
joint_type(id) = JointType.FIXED;

% id = 8;
% rpy = [1.5708;0;0];
% link_default_transform(1:4,1:4,id) = eye(4);
% link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
% link_default_transform(1:3,4,id) = [0;0;0.1358];
% link_com(1:3,id) = [0.00065123185041968; -0.0491929869131989; 0.00972258769184025];
% link_mass(id) = 0.025;
% link_inertia(1:3,1:3,id) = [0.00007371,-0.00000113,0.00000021;-0.00000113,0.00000781,-0.00001372;0.00000021,-0.00001372,0.0000747];
% joint_axis(1:3,id) = [0;0;-1];
% joint_type(id) = JointType.FIXED;

% id = 9;
% rpy = [1.5708;0;-3.1416];
% link_default_transform(1:4,1:4,id) = eye(4);
% link_default_transform(1:3,1:3,id) = rotz(rpy(3)*180/pi)*roty(rpy(2)*180/pi)*rotx(rpy(1)*180/pi);
% link_default_transform(1:3,4,id) = [0;0;0.1358];
% link_com(1:3,id) = [0.000651231850419722; -0.0491929869131991; 0.00972258769184024];
% link_mass(id) = 0.025;
% link_inertia(1:3,1:3,id) = [0.00007371,-0.00000113,0.00000021;-0.00000113,0.00000781,-0.00001372;0.00000021,-0.00001372,0.0000747];
% joint_axis(1:3,id) = [0;0;-1];
% joint_type(id) = JointType.FIXED;
% robot = struct();

robot.num_link = id;
robot.num_dof = 6;
% robot.base_transform = [roty(90),zeros(3,1);0,0,0,1];
robot.base_transform = eye(4);
robot.link_default_transform = link_default_transform;
robot.link_com = link_com;
robot.link_mass = link_mass;
robot.link_inertia = link_inertia;
robot.joint_axis = joint_axis;
robot.joint_type = joint_type;
robot.joint_limit = joint_limit;

clearvars -except robot
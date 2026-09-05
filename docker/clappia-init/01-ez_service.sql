-- Minimal local stand-in for the real `clappia_integration`.`ez_service` table
-- (the actual data lives on a shared external RDS server this app never
-- writes to). Empty on purpose -- just enough schema for ClappiaData queries
-- to succeed locally instead of erroring with "table doesn't exist".
CREATE TABLE IF NOT EXISTS `ez_service` (
  `submission_id` varchar(255) NOT NULL,
  `complaint_reg_date` date DEFAULT NULL,
  `service_id` varchar(255) NOT NULL,
  `machine_no` varchar(255) NOT NULL,
  `farmer_name` varchar(255) NOT NULL,
  `village` varchar(255) DEFAULT NULL,
  `taluka` varchar(255) DEFAULT NULL,
  `district` varchar(255) DEFAULT NULL,
  `state` varchar(255) DEFAULT NULL,
  `si_name` varchar(255) NOT NULL,
  `engineer_name` varchar(255) NOT NULL,
  `engineer_mail` varchar(255) NOT NULL,
  `status` varchar(50) NOT NULL,
  `faulty_power_card_no` varchar(255) DEFAULT NULL,
  `faulty_control_card_no` varchar(255) DEFAULT NULL,
  `component_1` varchar(255) DEFAULT NULL,
  `component_2` varchar(255) DEFAULT NULL,
  `component_3` varchar(255) DEFAULT NULL,
  `faulty_part_no_1` varchar(255) DEFAULT NULL,
  `faulty_part_no_2` varchar(255) DEFAULT NULL,
  `faulty_part_no_3` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`submission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

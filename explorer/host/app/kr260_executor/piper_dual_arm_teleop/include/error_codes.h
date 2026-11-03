/**
 * @file error_codes.h
 * @author pansamic (pansamic@foxmail.com)
 * @brief The definition of project error codes.
 * @version 0.1
 * @date 2025-07-10
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#ifndef __ERROR_CODES_H__
#define __ERROR_CODES_H__

enum ErrorCode
{
    OK = 0,
    InvalidArgument,
    Timeout,
    NotInitialized,
    NotImplemented,
    OutOfRange,
    HardwareFailure,
    CommunicationError,
    InvalidData,
    NoResult,
    UnknownError
};

#endif // _ERROR_CODES_H__
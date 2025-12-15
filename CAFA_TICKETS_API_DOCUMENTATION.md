# Cafa Tickets - Complete API Documentation

**Version:** 1.0  
**Base URL:** `http://localhost:8000/api/v1/`  
**Last Updated:** December 2025

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [User Management](#user-management)
4. [Event Categories](#event-categories)
5. [Event Operations](#event-operations)
6. [Ticket Purchase & Payments](#ticket-purchase--payments)
7. [Ticket Management](#ticket-management)
8. [Payment Profiles](#payment-profiles)
9. [Analytics & Dashboard](#analytics--dashboard)
10. [Error Handling](#error-handling)

---

## Getting Started

### Base URL
All API requests should be made to:
```
http://localhost:8000/api/v1/
```

### Authentication
Most endpoints require JWT authentication. Include the access token in the request header:
```
Authorization: Bearer {your_access_token}
```

### Date & Time Formats
- **Dates:** `YYYY-MM-DD` (e.g., "2025-07-15")
- **Times:** `HH:MM:SS` (e.g., "20:00:00")  
- **DateTimes:** ISO 8601 format (e.g., "2025-06-01T10:00:00Z")

---

## Authentication

### Register User
**POST** `/auth/users/`

Create a new user account.

**Request:**
```json
{
  "email": "john@example.com",
  "username": "johndoe",
  "password": "SecurePass123!",
  "re_password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "email": "john@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "id": 1
}
```

---

### Login
**POST** `/auth/login/`

Authenticate and receive access tokens.

**Request:**
```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "profile_image": "/media/profiles/john.jpg"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

---

See full documentation at: CAFA_TICKETS_API_DOCUMENTATION.md

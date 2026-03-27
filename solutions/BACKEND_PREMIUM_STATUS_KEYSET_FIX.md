# Backend - Premium Status Endpoint KeyError Fix

**Status**: 🔴 CRITICAL  
**Issue**: KeyError on `/api/v1/user-profiles/premium-status/` endpoint  
**Impact**: Frontend black screen, premium features non-functional  
**Severity**: High - Returns 500 error, breaks user discovery experience  
**Date Identified**: March 7, 2026

---

## Problem Description

### Error Details
```
ERROR 2026-03-07 20:04:22,245 log 14908 11216 Internal Server Error: /api/v1/user-profiles/premium-status/
KeyError: 'used'
File "D:\Projets\HIVMeet\env\hivmeet_backend\profiles\views_premium.py", line 100, in get
    'used': limits['limits']['super_likes']['used'],
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
```

### Root Cause

The `getPremiumStatus()` endpoint in `views_premium.py` (line 100) attempts to access:
```python
limits['limits']['super_likes']['used']
```

However, the data structure returned by the limits calculation service **does not contain the 'used' key**.

### Current Code (Broken)

**File**: `hivmeet_backend/profiles/views_premium.py` (lines 95-105)

```python
def get(self, request, *args, **kwargs):
    # ... authentication & validation ...
    
    limits = subscription_service.get_user_subscription_limits(user)
    
    return Response({
        'super_likes_used': limits['limits']['super_likes']['used'],  # ❌ KeyError
        'super_likes_remaining': limits['limits']['super_likes']['remaining'],
        'daily_likes_used': limits['limits']['daily_likes']['used'],   # ❌ Likely KeyError
        'daily_likes_remaining': limits['limits']['daily_likes']['remaining'],
        # ...
    })
```

### Impact Chain

```
Backend /api/v1/user-profiles/premium-status/ crashes
    ↓
Frontend DiscoveryBloc._loadDailyLimitInBackground() catches error silently
    ↓
Daily limits unavailable
    ↓
Premium features disabled (super likes tracker missing)
    ↓
⚠️ User sees black discovery screen or incomplete UI
```

---

## Solution

### Step 1: Identify Actual Data Structure

**Action**: Inspect what `subscription_service.get_user_subscription_limits()` actually returns.

**Command**:
```python
# In views_premium.py, temporarily add debug logging:
limits = subscription_service.get_user_subscription_limits(user)
print(f"DEBUG limits structure: {json.dumps(limits, indent=2, default=str)}")
```

**Expected Output** (example):
```json
{
  "limits": {
    "super_likes": {
      "total": 5,
      "remaining": 3
    },
    "daily_likes": {
      "total": 10,
      "remaining": 7
    }
  }
}
```

**Issue**: The 'used' key is **missing** - only 'remaining' is provided.

### Step 2: Fix the Endpoint

**File**: `hivmeet_backend/profiles/views_premium.py`

**Replace lines 95-125 with**:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_premium_status(request):
    """
    Get user's premium subscription status and daily limits.
    
    Response structure:
    {
        "subscription_active": bool,
        "subscription_plan": str,
        "subscription_expires_at": datetime or null,
        "super_likes": {
            "total": int,
            "remaining": int,
            "used": int (calculated as total - remaining),
            "reset_at": datetime
        },
        "daily_likes": {
            "total": int,
            "remaining": int,
            "used": int (calculated as total - remaining),
            "reset_at": datetime
        },
        "boosts": {
            "remaining": int,
            "next_reset_at": datetime
        }
    }
    """
    try:
        user = request.user
        
        # Get subscription limits from service
        limits_data = subscription_service.get_user_subscription_limits(user)
        
        # Safely extract nested dictionaries with defaults
        super_likes_limits = limits_data.get('limits', {}).get('super_likes', {})
        daily_likes_limits = limits_data.get('limits', {}).get('daily_likes', {})
        
        # Calculate 'used' from remaining and total
        super_likes_total = super_likes_limits.get('total', 0)
        super_likes_remaining = super_likes_limits.get('remaining', 0)
        super_likes_used = max(0, super_likes_total - super_likes_remaining)
        
        daily_likes_total = daily_likes_limits.get('total', 10)
        daily_likes_remaining = daily_likes_limits.get('remaining', 10)
        daily_likes_used = max(0, daily_likes_total - daily_likes_remaining)
        
        # Get subscription information
        subscription = user.subscription
        
        return Response({
            'subscription_active': subscription is not None and subscription.is_active,
            'subscription_plan': subscription.plan.name if subscription else 'free',
            'subscription_expires_at': subscription.expires_at if subscription else None,
            'super_likes': {
                'total': super_likes_total,
                'remaining': super_likes_remaining,
                'used': super_likes_used,
                'reset_at': super_likes_limits.get('reset_at'),
            },
            'daily_likes': {
                'total': daily_likes_total,
                'remaining': daily_likes_remaining,
                'used': daily_likes_used,
                'reset_at': daily_likes_limits.get('reset_at'),
            },
            'boosts': {
                'remaining': limits_data.get('limits', {}).get('boosts', {}).get('remaining', 0),
                'next_reset_at': limits_data.get('limits', {}).get('boosts', {}).get('reset_at'),
            },
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"ERROR in get_premium_status: {str(e)}")
        return Response({
            'error': 'subscription_fetch_failed',
            'message': 'Failed to retrieve premium status information',
            'detail': str(e) if settings.DEBUG else 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### Step 3: Add Error Handling

**File**: `hivmeet_backend/subscriptions/service.py`

Add validation to `get_user_subscription_limits()`:

```python
def get_user_subscription_limits(user):
    """
    Get user's subscription limits with safe default values.
    
    Returns:
    {
        'limits': {
            'super_likes': {
                'total': int,
                'remaining': int,
                'reset_at': datetime or None
            },
            'daily_likes': {
                'total': int,
                'remaining': int,
                'reset_at': datetime or None
            },
            'boosts': {
                'remaining': int,
                'reset_at': datetime or None
            }
        }
    }
    """
    try:
        subscription = user.subscription
        
        if not subscription or not subscription.is_active:
            # Free user defaults
            return {
                'limits': {
                    'super_likes': {
                        'total': 0,
                        'remaining': 0,
                        'reset_at': None,
                    },
                    'daily_likes': {
                        'total': 10,
                        'remaining': get_remaining_daily_likes(user),
                        'reset_at': get_daily_reset_time(),
                    },
                    'boosts': {
                        'remaining': 0,
                        'reset_at': None,
                    }
                }
            }
        
        # Premium user limits
        plan = subscription.plan
        
        return {
            'limits': {
                'super_likes': {
                    'total': plan.super_likes_per_day,
                    'remaining': get_remaining_super_likes(user),
                    'reset_at': get_daily_reset_time(),
                },
                'daily_likes': {
                    'total': plan.likes_per_day,
                    'remaining': get_remaining_daily_likes(user),
                    'reset_at': get_daily_reset_time(),
                },
                'boosts': {
                    'remaining': subscription.boosts_remaining,
                    'reset_at': subscription.next_boost_reset_at,
                }
            }
        }
    except Exception as e:
        logger.error(f"Error calculating subscription limits for user {user.id}: {str(e)}")
        # Return safe defaults on error
        return {
            'limits': {
                'super_likes': {'total': 0, 'remaining': 0, 'reset_at': None},
                'daily_likes': {'total': 10, 'remaining': 10, 'reset_at': None},
                'boosts': {'remaining': 0, 'reset_at': None},
            }
        }
```

---

## Testing

### Frontend Test
```dart
// lib/data/repositories/match_repository_impl_test.dart
test('getDailyLikeLimit should extract limits from premium-status response', () async {
  final mockResponse = Response(
    requestOptions: RequestOptions(path: '/api/v1/user-profiles/premium-status/'),
    statusCode: 200,
    data: {
      'daily_likes': {
        'total': 10,
        'remaining': 7,
        'used': 3,
        'reset_at': '2026-03-08T00:00:00Z',
      },
      'super_likes': {
        'total': 5,
        'remaining': 2,
        'used': 3,
        'reset_at': '2026-03-08T00:00:00Z',
      },
    }
  );
  
  when(mockMatchingApi.getPremiumStatus()).thenAnswer((_) async => mockResponse);
  
  final result = await repository.getDailyLikeLimit();
  
  expect(result.isRight(), true);
  result.fold(
    (failure) => fail('Should not return failure'),
    (dailyLimit) {
      expect(dailyLimit.remainingLikes, 7);
      expect(dailyLimit.totalLikes, 10);
      expect(dailyLimit.resetAt, DateTime.parse('2026-03-08T00:00:00Z'));
    }
  );
});
```

### Backend Test
```python
# hivmeet_backend/profiles/test_views_premium.py
def test_get_premium_status_returns_correct_structure(authenticated_client, user_with_premium):
    """Verify premium-status endpoint returns all required fields."""
    response = authenticated_client.get('/api/v1/user-profiles/premium-status/')
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify structure
    assert 'super_likes' in data
    assert 'daily_likes' in data
    assert 'boosts' in data
    
    # Verify each section has both 'remaining' and 'used'
    assert 'total' in data['super_likes']
    assert 'remaining' in data['super_likes']
    assert 'used' in data['super_likes']
    
    assert 'total' in data['daily_likes']
    assert 'remaining' in data['daily_likes']
    assert 'used' in data['daily_likes']
    
    # Verify math consistency
    assert data['super_likes']['used'] == (
        data['super_likes']['total'] - 
        data['super_likes']['remaining']
    )
```

---

## Deployment Checklist

- [ ] Fix `views_premium.py` to handle missing 'used' key
- [ ] Update `subscription_service.py` to return consistent structure
- [ ] Add proper error handling with fallback defaults
- [ ] Add unit tests for both endpoints
- [ ] Test with free user (should return 0 super_likes)
- [ ] Test with premium user (should return correct counts)
- [ ] Verify frontend receives properly structured response
- [ ] Verify frontend daily limit indicator displays correctly
- [ ] Deploy and monitor error logs

---

## Context

This issue affects the **Discovery Page** which loads premium status in the background to show daily like counter and super like remaining count. The frontend silently handles errors but users then miss critical UI elements.

**Frontend**: Discovery page navigates successfully but key premium indicators are missing or show defaults (all 0s).

**Backend**: Unhandled KeyError causing 500 Internal Server Error responses that break the premium features experience.


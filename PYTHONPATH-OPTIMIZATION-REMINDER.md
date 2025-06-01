# 🚨 REMINDER: PYTHONPATH Virtual Environment Optimization

## 📍 Context
When working on the `feature/multi-qiskit-venvs` branch, there's a significant opportunity to optimize disk space usage through PYTHONPATH manipulation instead of separate virtual environments.

## 💡 The Opportunity
**Current approach**: 3 separate virtual environments (~1.05GB)
- RQB2 (Qiskit 2.x latest) 
- RQB2-v14 (Qiskit 1.4)
- RQB2-v044 (Qiskit 0.44) - currently disabled

**Proposed approach**: Single unified environment (~430MB)
- One Python interpreter
- Shared common dependencies (numpy, matplotlib, etc.)
- Version-specific imports via PYTHONPATH manipulation
- **Space savings: ~620MB (59% reduction)**

## 🔧 Implementation Files Created
- `qiskit-version-manager.py` - Python class for version switching
- `menu-integration-example.sh` - Updated bash functions  
- `space-optimization-proposal.md` - Detailed technical proposal
- `pythonpath-demo.py` - Technical demonstration

## 🎯 Next Steps When Returning
1. Review current image size results from compression optimization
2. If still needed, implement unified virtual environment approach
3. Test compatibility with existing demos
4. Update installation scripts in `stage-RQB2/01-install-qiskit/`

## 📊 Expected Impact
- **Disk space**: 59% reduction in venv footprint
- **Build time**: Faster due to single environment setup
- **Compatibility**: Maintained through PYTHONPATH switching
- **Maintenance**: Simpler single environment management

---
*Created: 2025-06-01 - Branch: feature/multi-qiskit-venvs*
*Status: Ready for implementation if image size optimization is still needed*